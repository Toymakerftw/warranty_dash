from flask_login import UserMixin
from app.database import get_user_by_id

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.email = user_data['email']
        self.first_name = user_data.get('first_name')
        self.last_name = user_data.get('last_name')
        self.role = user_data.get('role', 'user')
        self._is_active = bool(user_data.get('is_active', 1))
        self.created_at = user_data.get('created_at')
        self.last_login = user_data.get('last_login')
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_active(self):
        return self._is_active
    
    def get_id(self):
        return str(self.id)
    
    @staticmethod
    def get(user_id):
        user_data = get_user_by_id(user_id)
        if user_data:
            return User(user_data)
        return None 