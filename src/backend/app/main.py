try:
    from .database.createDatabase import create_database
    from .database.fillDatabase import fill_database
except ImportError:
    from database.createDatabase import create_database
    from database.fillDatabase import fill_database


if __name__ == "__main__":
    create_database()
    fill_database()
