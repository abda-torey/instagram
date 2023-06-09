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
        (diff.seconds / 3600, 'hr', 'hrs'),
        (diff.seconds / 60, 'min', 'mins'),
        (diff.seconds, 'sec', 'secs'),
    )
    for period, singular, plural in periods:
        if period >= 1:
            return '%d %s ago' % (period, singular if period == 1 else plural)
    return default


app.jinja_env.filters['timesince'] = format_timesince

# update a post's comment


def updatePostComments(post_id, new_comment):
    key = datastore_client.key('Post', int(post_id))
    post = datastore_client.get(key)
    if post is None:
        return
    comments = post.get('comments', [])
    comments.append(new_comment)

    # Update the post entity with the new comments
    post['comments'] = comments
    datastore_client.put(post)


# retrirve the posts for the user and all the users they follow
def get_posts_for_user_and_following(user_id):
    following = User.get_following(user_id)
    print(len(following))
    following.append(user_id)  # Include user's own posts as well
    posts = []
    for user in following:
        query = datastore_client.query(kind='Post')
        query.add_filter('user_id', '=', user)
        query.order = ['-created_at']
        # search for results and Limit the number of posts returned to 50
        user_posts = list(query.fetch(limit=50))
        for post in user_posts:
            # Get the blob name from the datastore entity
            # Reverse the order of the comments array
            comments = post.get('comments', [])
            post['comments'] = list(reversed(comments))
            blob_name = post.get('image_blob')
            if blob_name:
                blob = storage_client.bucket(
                    PROJECT_STORAGE_BUCKET).get_blob(blob_name)
                expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                post['image_url'] = blob.generate_signed_url(
                    expiration=expiration, method='GET')
        posts.extend(user_posts)
    return posts


# retrieve posts for specified user
def get_posts_for_user(user_id):
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
    return posts


# display list of following for a user
@app.route('/getfollowing')
def getfollowing():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    userDetails = None
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            userDetails = User.getUserDetails(claims['user_id'])
            following_list = User.get_following(claims['user_id'])
            followers_list = User.get_followers(claims['user_id'])
            following_list_length = len(following_list)
            followers_list_length = len(followers_list)

            users = []
            for user in following_list:
                user = User.getUserDetails(user)
                users.append(user)
        except ValueError as exc:
            error_message = str(exc)

    return render_template('following.html', followers_list_length=followers_list_length, users=users,
                           userDetails=userDetails, user=claims,
                             error_message=error_message, following_list_length=following_list_length)


# display list of followers for a user
@app.route('/getfollowers')
def getfollowers():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    userDetails = None
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            userDetails = User.getUserDetails(claims['user_id'])
            following_list = User.get_following(claims['user_id'])
            followers_list = User.get_followers(claims['user_id'])
            following_list_length = len(following_list)
            followers_list_length = len(followers_list)

            users = []
            for user in followers_list:
                user = User.getUserDetails(user)
                users.append(user)
            
            
        except ValueError as exc:
            error_message = str(exc)

    return render_template('followers.html',users=users,following_list = following_list, followers_list_length=followers_list_length,
                           userDetails=userDetails, user=claims, error_message=error_message, following_list_length=following_list_length)


# display profile of the user clicked
@app.route('/show_profile/<user_id>')
def show_profile(user_id):
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    posts = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            posts = get_posts_for_user(user_id)
            following_list = User.get_following(claims['user_id'])
            userDetails = User.getUserDetails(claims['user_id'])
            user_beingChecked_details = User.getUserDetails(user_id)
            user_beingChecked_followingListLength = len(
                User.get_following(user_id))
            user_beingChecked_followersListLength = len(
                User.get_followers(user_id))
        except ValueError as exc:
            error_message = str(exc)

    return render_template('show_profile.html',following_list = following_list, user_beingChecked_followersListLength=user_beingChecked_followersListLength,
                           user_beingChecked_followingListLength=user_beingChecked_followingListLength,
                           userDetails=userDetails, user_beingChecked_details=user_beingChecked_details,
                           error_message=error_message, user_profile_beingchecked=user_id, posts=posts)


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
    return redirect(url_for('root'))


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

            users = User.search_users(query,user_id)

            following_list = User.get_following(user_id)
            userDetails = User.getUserDetails(claims['user_id'])
        except ValueError as exc:
            error_message = str(exc)

    return render_template('search_users.html', users=users, userDetails=userDetails, following_list=following_list)


@app.route('/add_comment', methods=['POST'])
def add_comment():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            userDetails = User.getUserDetails(claims['user_id'])
            post_id = request.form['post_id']
            comment = request.form['comment_text']
            new_comment = {
                'user_id': claims['user_id'],
                'username': userDetails['username'],
                'comment_text': comment,
                'created_at': datetime.datetime.utcnow()
            }
            print(comment)
            print('post ID is:', post_id)
            print('this my newComment', new_comment)
            updatePostComments(post_id, new_comment)
        except ValueError as exc:
            error_message = str(exc)
    return redirect(url_for('root'))


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
            userDetails = User.getUserDetails(user_id)
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
            post_entity['username'] = userDetails['username']
            post_entity['image_blob'] = blob.name
            post_entity['caption'] = post_caption
            post_entity['comments'] = []
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
            posts = get_posts_for_user(user_id)
            
            userDetails = User.getUserDetails(claims['user_id'])
            following_list = User.get_following(user_id)
            followers_list = User.get_followers(user_id)
            following_list_length = len(following_list)
            followers_list_length = len(followers_list)
        except ValueError as exc:
            error_message = str(exc)
    return render_template('profile.html', followers_list_length=followers_list_length,
                           userDetails=userDetails, user=claims, error_message=error_message, posts=posts, following_list_length=following_list_length)


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


@app.route('/profile_name_firsttym')
def profile_name_firsttym():
    id_token = request.cookies.get("token")
    error_message = request.args.get('error_message')
    claims = None
    email = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)

        except ValueError as exc:
            error_message = str(exc)
    return render_template('profile_name.html', user_id=claims['user_id'], error_message=error_message)


@app.route('/add_profile_name', methods=['POST'])
def add_profile_name():
    error_message = None
    user_id = request.form['user_id']
    profile_name = request.form['profile_name']
    username = request.form['username']
    if profile_name:
        profile_name = profile_name.lower()
        print(profile_name)
        username = username.lower()
    try:
        User.updateProfileName(user_id, profile_name, username)
    except ValueError as exc:
        error_message = "UserName already exists"
        return redirect(url_for('profile_name_firsttym', error_message=error_message))
    return redirect(url_for('root'))


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
            userDetails = User.getUserDetails(claims['user_id'])

            if not userDetails:
                User.create_user(claims['user_id'], claims['email'])
                return redirect(url_for('profile_name_firsttym'))

            userDetails = User.getUserDetails(claims['user_id'])

            posts = get_posts_for_user_and_following(claims['user_id'])

        except ValueError as exc:
            error_message = str(exc)
    return render_template('index.html', posts=posts, userDetails=userDetails, error_message=error_message)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
