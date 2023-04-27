from datetime import datetime,timezone
import pytz
import datetime

import random
import uuid
from google.cloud import storage
import google.oauth2.id_token
from flask import Flask, render_template, request, redirect, Response, url_for
from google.auth.transport import requests
from local_constants import PROJECT_NAME, PROJECT_STORAGE_BUCKET

from google.cloud import datastore
app = Flask(__name__)
datastore_client = datastore.Client()
firebase_request_adapter = requests.Request()
# Initialize Google Cloud Storage client
storage_client = storage.Client(project=PROJECT_NAME)


# filter for timesince

def format_timesince(dt, default='just now'):
    """
    Returns string representing 'time since' e.g.
    3 days ago, 5 hours ago etc.
    """
    if dt is None:
        return ''
    
    
    # Get the current datetime in UTC
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    created_at_aware = dt.replace(tzinfo=pytz.UTC)
    diff = now - created_at_aware
    periods = (
        (diff.days / 365, 'year', 'years'),
        (diff.days / 30, 'month', 'months'),
        (diff.days / 7, 'week', 'weeks'),
        (diff.days, 'day', 'days'),
        (diff.seconds / 3600, 'hour', 'hours'),
        (diff.seconds / 60, 'minute', 'minutes'),
        (diff.seconds, 'second', 'seconds'),
    )
    for period, singular, plural in periods:
        if period >= 1:
            return '%d %s ago' % (period, singular if period == 1 else plural)
    return default

app.jinja_env.filters['timesince'] = format_timesince


def create_user(user_id, name, email):
    entity_key = datastore_client.key('Users', user_id)

    entity = datastore_client.get(entity_key)

    if entity is not None:
        return

    entity = datastore.Entity(key=entity_key)
    entity.update({

        'name': name,
        'email': email,
        'following': [],
        'followers': []
    })
    datastore_client.put(entity)


@app.route('/create_post', methods=['POST'])
def create_post():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    result = None
    user_info = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            user_id = claims['user_id']
            # Get the image file and caption from the form data
            post_image = request.files['postImage']
            post_caption = request.form['postCaption']
            # Upload the image file to Google Cloud Storage with user ID as part of Blob's name
            blob_name = f'{user_id}_{post_image.filename}'
            blob = storage_client.bucket(
                PROJECT_STORAGE_BUCKET).blob(blob_name)
            blob.upload_from_file(post_image)
            # Store the post caption and blob name in Google Cloud Datastore
            post_entity = datastore.Entity(key=datastore_client.key('Post'))
            post_entity['user_id'] = user_id
            post_entity['image_blob'] = blob.name
            post_entity['caption'] = post_caption
            post_entity['created_at'] = datetime.datetime.utcnow()
            datastore_client.put(post_entity)

        except ValueError as exc:
            error_message = str(exc)
    return redirect(url_for('root'))


@app.route('/user_posts/<user_id>')
def user_posts(user_id):

    # Render the posts and their images in a template
    return render_template('user_posts.html', posts=posts)


@app.route('/displayProfile')
def displayProfile():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    posts = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            user_id = claims['user_id']
            # Query posts from Google Cloud Datastore for the specified user ID
            query = datastore_client.query(kind='Post')
            query.add_filter('user_id', '=', user_id)
            query.order = ['-created_at']
            posts = list(query.fetch())

            # Retrieve the image Blob for each post and add it to the post object
            for post in posts:
                # Get the blob name from the datastore entity
                blob_name = post.get('image_blob')
                if blob_name:
                    blob = storage_client.bucket(
                        PROJECT_STORAGE_BUCKET).get_blob(blob_name)
                    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                    post['image_url'] = blob.generate_signed_url(
                        expiration=expiration, method='GET')

        except ValueError as exc:
            error_message = str(exc)
    return render_template('profile.html', user=claims, error_message=error_message, posts=posts)


@app.route('/addPost')
def addPost():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)

        except ValueError as exc:
            error_message = str(exc)
    return render_template('add_post.html', user=claims, error_message=error_message)


@app.route('/')
def root():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    posts = None
    user_info = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            name = request.cookies.get("name")
            if name:
                name = name.lower()
            create_user(claims['user_id'], name, claims['email'])

        except ValueError as exc:
            error_message = str(exc)
    return render_template('index.html', user=claims, error_message=error_message)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
