from flask_login import UserMixin
import hashlib
import uuid
import psycopg2
import psycopg2.extras
import dblib


class User(UserMixin):
    """
    A registered user that can log into the trial2rev system
    """

    def __init__(self, email, nickname, password, permissions):
        """
        Init user from kwargs
        @param email: unique email address used to login
        @param nickname: alias that is visible by other users
        @param password: used to login
        @param permissions: admin or standard
        """
        conn = dblib.create_con(VERBOSE=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE user_name = %s", (email,))
        user = cur.fetchone()
        if user is None:
            self.id = unicode(email)
            password, salt = self.set_password(password)
            self.permissions = permissions
            self.nickname = nickname
            cur.execute(
                "INSERT INTO users (user_name, nickname, user_type, salt, salted_password) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (user_name) DO NOTHING RETURNING ID;",
                (email, nickname, permissions, salt, password))
            conn.commit()
            self.db_id = cur.fetchone()
        else:
            self.id = user['user_name']
            self.password = user['salted_password']
            self.salt = user['salt']
            self.permissions = user['user_type']
            self.nickname = user['nickname']
            self.db_id = user['id']
        conn.close()


    def set_password(self, password):
        """
        gen password hash and salt
        @param password: user specified password
        @return: [hash, salt]
        """
        salt = uuid.uuid4().hex
        return [hashlib.sha256(salt.encode() + str(password).encode()).hexdigest(), salt]

    def change_password(self, hashed_password):
        """
        change user password
        @param hashed_password:
        """
        conn = dblib.create_con(VERBOSE=True)
        cur = conn.cursor()
        cur.execute(
            "UPDATE users set (salted_password, salt) = (%s, %s) where (user_name) = (%s);",
            (hashed_password[0], hashed_password[1],self.id ))
        conn.commit()
        conn.close()

    def check_password(self,user_password):
        """
        verify that user_password matches password belonging to this user
        @param user_password:
        @return: boolean
        """
        password = str(self.password)
        salt = self.salt
        print hashlib.sha256(salt.encode() + str(user_password).encode()).hexdigest()
        return password == hashlib.sha256(salt.encode() + str(user_password).encode()).hexdigest()

    @property
    def is_admin(self):
        """
        check if this user is an admin
        @return: boolean
        """
        if self.permissions == 'admin':
            return True
        else:
            return False

    @property
    def is_authenticated(self):
        """
        check if user is logged in
        @return: boolean
        """
        return True

    @classmethod
    def delete(cls, id):
        """
        remove user with id
        @param id: user_id to remove
        """
        conn = dblib.create_con(VERBOSE=True)
        if conn:
            cur = conn.cursor()
            cur.execute("DELETE from users where user_name = (%s)", (id,))
        conn.commit()
        conn.close()

    @classmethod
    def get(cls, id):
        """
        get user by id
        @param id: id of desired user
        @return: User instance
        """
        conn = dblib.create_con(VERBOSE=True)
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * from users where user_name = (%s);", (id,))
            user = cursor.fetchone()
            if user is not None:
                return User(user['user_name'], user['nickname'], user['salted_password'],user['user_type'])
            else:
                return None


    @classmethod
    def get_all(cls):
        """
        @return: a list of all User instances
        """
        conn = dblib.create_con(VERBOSE=True)
        cursor = conn.cursor()
        cursor.execute("select user_name from users;")
        usrs = cursor.fetchall()
        objs = map(lambda u: cls.get(u),list(zip(*usrs)[0]))
        return objs


