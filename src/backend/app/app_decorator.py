import logging
from functools import wraps
import jwt

from flask import request, jsonify, g

logger = logging.getLogger(__name__)

# Valid roles for access control.
VALID_ROLES = {'guest', 'student', 'employee', 'admin'}

# Decorator to enforce role-based access control on Flask routes.
# https://www.youtube.com/watch?v=U-G-mSd4KAE
def role_required(*roles, app):

    def set_guest_context():
        g.current_user = {'username': 'guest', 'groups': ['guest']}
        g.current_roles = {'guest'}
        logger.info('Guest context set for %s', request.path)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            header = request.headers.get('Authorization', '')

            if header.startswith('Bearer '):
                token = header.split(' ', 1)[1].strip()
            else:
                token = request.cookies.get('token')

            if not token:
                if roles and 'guest' in roles:
                    logger.info('Guest access allowed for %s', request.path)
                    set_guest_context()
                    return func(*args, **kwargs)
                logger.warning('Missing token for %s', request.path)
                return jsonify({'message': 'Missing or invalid Authorization header'}), 401

            try:
                payload = jwt.decode(token,
                                     app.config['SECRET_KEY'],
                                     algorithms=['HS256'])
                user_roles = set(payload.get('groups') or [])
                valid_user_roles = user_roles & VALID_ROLES
                if not valid_user_roles:
                    logger.warning('Unknown role for %s', request.path)
                    return jsonify({'message': 'Unknown user role'}), 403

                g.current_user = payload
                g.current_roles = valid_user_roles
                logger.info("User '%s' authenticated for %s",
                            payload.get('username', 'unknown'),
                            request.path)
            except jwt.ExpiredSignatureError:
                logger.info('Expired token for %s', request.path)
                set_guest_context()
            except jwt.InvalidTokenError:
                logger.warning('Invalid token for %s', request.path)
                return jsonify({'message': 'Invalid token'}), 401

            if roles and not g.current_roles & set(roles):
                logger.warning('Insufficient role for %s', request.path)
                return jsonify({'message': 'Insufficient role'}), 403

            logger.info('Access granted for %s', request.path)
            return func(*args, **kwargs)
        return wrapper
    return decorator