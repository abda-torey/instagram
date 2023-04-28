from datetime import datetime, timezone
import pytz
import datetime
from models.user import User
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


def get_posts_for_user_and_following(user_id):
    following = User.get_following(user_id)
    following.append(user_id)  # Include user's own posts as well
    posts = []
    for user in following:
        user_key = datastore_client.key('Users', user)
        query = datastore_client.query(kind='Post')
        query.add_filter('user_id', '=', user_key)
        query.order = ['-created_at']
        posts = list(query.fetch())
        for post in posts:
            # Get the blob name from the datastore entity
            blob_name = post.get('image_blob')
            if blob_name:
                blob = storage_client.bucket(
                    PROJECT_STORAGE_BUCKET).get_blob(blob_name)
                expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                post['image_url'] = blob.generate_signed_url(
                    expiration=expiration, method='GET')
    return posts


@app.route('/unfollow/<user_id_to_unfollow>')
def unfollow(user_id_to_unfollow):
    id_token = request.cookies.get("token")
    error_message = None
    claims = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            current_user_id = claims['user_id']
            # unfollow the user
            User.unfollow_user(current_user_id, user_id_to_unfollow)
            User.updateFollowersList(
                current_id_user=user_id_to_unfollow, user_id_remove_from_follower=current_user_id)

        except ValueError as exc:
            error_message = str(exc)

    # redirect back to the search results page
    return redirect(url_for('displayProfile'))


@app.route('/follow/<user_id_to_follow>')
def follow(user_id_to_follow):
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    userDetails = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            current_user_id = claims['user_id']
            # follow the user
            User.follow_user(current_user_id, user_id_to_follow)
            # update followers list of the user followed
            User.update_follower(
                user_id_followed=user_id_to_follow, followed_by_id=current_user_id)

        except ValueError as exc:
            error_message = str(exc)

    # redirect back to the search results page
    return redirect(url_for('displayProfile'))


@app.route('/search_user', methods=['POST'])
def searchUsers():

    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    users = None
    userDetails = None
    following_list = None
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            user_id = claims['user_id']
            query = request.form['query']
            if query:
                query = query.lower()

            users = User.search_users(query)

            following_list = User.get_following(user_id)
            userDetails = User.getUserDetails(claims['user_id'])
            for user in users:
                if user['id'] not in following_list:
                    print(user['name'], 'is not followed by you')
                else:
                    print(user['name'], 'is followed by you')
        except ValueError as exc:
            error_message = str(exc)

    return render_template('search_users.html', users=users, userDetails=userDetails, following_list=following_list)


@app.route('/create_post', methods=['POST'])
def create_post():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    result = None
    userDetails = None

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
    userDetails = None

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
            userDetails = User.getUserDetails(claims['user_id'])
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
            following_list = User.get_following(user_id)
            following_list_length = len(following_list)
        except ValueError as exc:
            error_message = str(exc)
    return render_template('profile.html', userDetails=userDetails, user=claims, error_message=error_message, posts=posts, following_list_length=following_list_length)


@app.route('/addPost')
def addPost():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            userDetails = User.getUserDetails(claims['user_id'])
        except ValueError as exc:
            error_message = str(exc)
    return render_template('add_post.html', userDetails=userDetails, user=claims, error_message=error_message)


@app.route('/')
def root():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    posts = None
    userDetails = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            name = request.cookies.get("name")
            if name:
                name = name.lower()
            User.create_user(claims['user_id'], name, claims['email'])
            userDetails = User.getUserDetails(claims['user_id'])
            posts = get_posts_for_user_and_following(claims['user_id'])
            for post in posts:
                print('posts are: ',posts)
        except ValueError as exc:
            error_message = str(exc)
    return render_template('index.html', userDetails=userDetails, error_message=error_message)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
