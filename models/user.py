

import google.oauth2.id_token
from google.cloud import datastore

datastore_client = datastore.Client()


class User:
    def create_user(user_id, name, email):
        # Check if email already exists
        query = datastore_client.query(kind='Users')
        query.add_filter('email', '=', email)
        result = list(query.fetch())
        if len(result) > 0:
            return

        # Create new user
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

    def getUserDetails(user_id):
        entity_key = datastore_client.key('Users', user_id)
        entity = datastore_client.get(entity_key)
        return entity

    def follow_user(current_user_id, user_id_to_follow):
        # get the current user entity from the datastore
        current_user_key = datastore_client.key('Users', current_user_id)
        current_user = datastore_client.get(current_user_key)

        # add the user_id to follow to the current user's following array
        if user_id_to_follow not in current_user['following']:
            current_user['following'].append(user_id_to_follow)
            datastore_client.put(current_user)
            return True
        else:
            return False

    def unfollow_user(current_user_id, user_id_to_unfollow):
        # get the current user entity from the datastore
        current_user_key = datastore_client.key('Users', current_user_id)
        current_user = datastore_client.get(current_user_key)

        # remove the user_id to unfollow from the current user's following array
        if user_id_to_unfollow in current_user['following']:
            current_user['following'].remove(user_id_to_unfollow)
            datastore_client.put(current_user)
            return True
        else:
            return False

    def updateFollowersList(current_id_user, user_id_remove_from_follower):
        # get the entity of the user unfollowed
        unfollowed_user_key = datastore_client.key(
            'Users', current_id_user)
        unfollowed_user = datastore_client.get(unfollowed_user_key)
        # remove the user_id unfollowed from their followers list
        if user_id_remove_from_follower in unfollowed_user['followers']:
            unfollowed_user['followers'].remove(
                user_id_remove_from_follower)
            datastore_client.put(unfollowed_user)

            return True
        else:
            return False

    # code to update the follower list of the user followed

    def update_follower(user_id_followed, followed_by_id):
        # get the  entity of the user followed from the datastore
        user_followed_key = datastore_client.key('Users', user_id_followed)
        current_user = datastore_client.get(user_followed_key)

        # add the followed_by_id  to the current user's followers array
        if followed_by_id not in current_user['followers']:
            current_user['followers'].append(followed_by_id)
            datastore_client.put(current_user)
            return True
        else:
            return False
    # search for users

    def search_users(query):
        query = query.lower()
        query_filter = datastore_client.query(kind='Users')
        query_filter.add_filter('name', '>=', query)
        query_filter.add_filter('name', '<', query + u'\ufffd')
        query_results = query_filter.fetch()

        users = []
        for result in query_results:
            users.append({
                'id': result.key.id_or_name,
                'name': result['name'],
                'email': result['email']
            })

        return users

    def get_following(user_id):
        user_key = datastore_client.key('Users', user_id)
        user = datastore_client.get(user_key)

        if user is None:
            return []

        following = user.get('following', [])

        return following
