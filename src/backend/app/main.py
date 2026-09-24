try:
    from .database.createDatabase import create_database
    from .database.fillDatabase import fill_database
except ImportError:
    from database.createDatabase import create_database
    from database.fillDatabase import fill_database

# Creates the database and fills it with data when the script is run directly

if __name__ == "__main__":
    create_database()  # Creates the database and tables
    fill_database()  # Fills the database with data
