#!/usr/bin/env python3
"""
Database migration to add ChannelMapping table.
Run this script to update your database schema.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.user import ChannelMapping

def upgrade():
    """Add the ChannelMapping table."""
    app = create_app()
    with app.app_context():
        # Create the table
        db.create_all()
        print("ChannelMapping table created successfully!")

if __name__ == '__main__':
    upgrade()