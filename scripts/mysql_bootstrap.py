import os

import MySQLdb


def main() -> None:
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    db_name = os.getenv("MYSQL_NAME", "farmer_db")

    if not password:
        raise SystemExit("MYSQL_PASSWORD is not set")

    conn = MySQLdb.connect(host=host, port=port, user=user, passwd=password)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute("SHOW DATABASES LIKE %s", (db_name,))
        row = cursor.fetchone()
        print("DB_EXISTS:", row)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
