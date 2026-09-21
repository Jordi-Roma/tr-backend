import sys
import os

# Add the parent directory to sys.path so we can import app
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.database.connection import get_connection

def run_migration():
    print("Running migration...")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            ALTER TABLE categoria
            ADD COLUMN IF NOT EXISTS categoria_padre_id BIGINT NULL;
            """)
            
            # Check if constraint exists before adding
            cur.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'categoria' AND constraint_name = 'fk_categoria_padre';
            """)
            if not cur.fetchone():
                cur.execute("""
                ALTER TABLE categoria
                ADD CONSTRAINT fk_categoria_padre
                FOREIGN KEY (categoria_padre_id) REFERENCES categoria (id)
                ON UPDATE CASCADE ON DELETE RESTRICT;
                """)
        conn.commit()
        print("Migration successful.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
