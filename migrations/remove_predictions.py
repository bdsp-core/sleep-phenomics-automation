#!/usr/bin/env python3
"""
Database migration to remove prediction-related columns.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db

def upgrade():
    """Remove prediction-related columns from the database."""
    app = create_app()
    with app.app_context():
        # For SQLite, we need to recreate the table without the has_predictions column
        # This is a simplified approach - in production you'd use proper migration tools
        
        try:
            # Check if the column exists
            with db.engine.connect() as conn:
                result = conn.execute(db.text("PRAGMA table_info(eeg_file)"))
                columns = [row[1] for row in result]
                
                if 'has_predictions' in columns:
                    print("Removing has_predictions column...")
                    
                    # Create new table without has_predictions
                    conn.execute(db.text("""
                        CREATE TABLE eeg_file_new (
                            id INTEGER PRIMARY KEY,
                            filename VARCHAR,
                            original_filename VARCHAR,
                            upload_date DATETIME,
                            file_size INTEGER,
                            storage_path VARCHAR,
                            sampling_rate FLOAT,
                            num_channels INTEGER,
                            duration FLOAT,
                            recording_date DATETIME,
                            has_spectrogram BOOLEAN,
                            user_id INTEGER,
                            FOREIGN KEY(user_id) REFERENCES user (id)
                        )
                    """))
                    
                    # Copy data from old table to new table
                    conn.execute(db.text("""
                        INSERT INTO eeg_file_new 
                        SELECT id, filename, original_filename, upload_date, file_size, 
                               storage_path, sampling_rate, num_channels, duration, 
                               recording_date, has_spectrogram, user_id
                        FROM eeg_file
                    """))
                    
                    # Drop old table and rename new table
                    conn.execute(db.text("DROP TABLE eeg_file"))
                    conn.execute(db.text("ALTER TABLE eeg_file_new RENAME TO eeg_file"))
                    conn.commit()
                    
                    print("✓ has_predictions column removed successfully!")
                else:
                    print("✓ has_predictions column already removed")
                
                # Also clean up any prediction/report derived files
                result = conn.execute(db.text("SELECT * FROM derived_file WHERE file_type IN ('csv', 'txt')"))
                rows = result.fetchall()
                if rows:
                    print(f"Removing {len(rows)} prediction/report derived files...")
                    conn.execute(db.text("DELETE FROM derived_file WHERE file_type IN ('csv', 'txt')"))
                    conn.commit()
                    print("✓ Prediction/report files removed")
                else:
                    print("✓ No prediction/report files to remove")
                
        except Exception as e:
            print(f"Error during migration: {e}")
            raise

if __name__ == '__main__':
    upgrade()