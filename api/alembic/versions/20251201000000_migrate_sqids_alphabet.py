"""migrate sqids alphabet

Revision ID: 20251201000000
Revises: 20251128000000
Create Date: 2025-12-01 00:00:00.000000

This migration re-encodes all existing public_sqid values from SQIDS_ALPHABET
to NEW_SQIDS_ALPHABET (removing ambiguous characters: 0, o, O, 1, l, I).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "20251201000000"
down_revision = "20250131000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Re-encode all public_sqid values using NEW_SQIDS_ALPHABET.
    
    Process:
    1. Decode each public_sqid using OLD alphabet to get integer id
    2. Re-encode using NEW alphabet
    3. Update the public_sqid column
    """
    import os
    from sqids import Sqids
    
    # Get alphabets from environment
    old_alphabet = os.getenv("SQIDS_ALPHABET", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    new_alphabet = os.getenv("NEW_SQIDS_ALPHABET", old_alphabet)
    
    # Create Sqids instances
    sqids_old = Sqids(alphabet=old_alphabet, min_length=0)
    sqids_new = Sqids(alphabet=new_alphabet, min_length=0)
    
    # Get connection
    connection = op.get_bind()
    
    # Fetch all posts with their public_sqid and id
    result = connection.execute(text("SELECT id, public_sqid FROM posts WHERE public_sqid IS NOT NULL"))
    posts = result.fetchall()
    
    # Re-encode each post
    updated_count = 0
    for post_id, old_sqid in posts:
        try:
            # Decode using old alphabet
            decoded = sqids_old.decode(old_sqid)
            if decoded and len(decoded) == 1:
                # Re-encode using new alphabet
                new_sqid = sqids_new.encode([decoded[0]])
                
                # Verify we got the same post_id
                if decoded[0] == post_id:
                    # Update the public_sqid
                    connection.execute(
                        text("UPDATE posts SET public_sqid = :new_sqid WHERE id = :id"),
                        {"new_sqid": new_sqid, "id": post_id}
                    )
                    updated_count += 1
                else:
                    print(f"Warning: Post {post_id} decoded to {decoded[0]}, skipping")
            else:
                print(f"Warning: Post {post_id} has invalid sqid {old_sqid}, skipping")
        except Exception as e:
            print(f"Error processing post {post_id} with sqid {old_sqid}: {e}")
    
    print(f"Migrated {updated_count} posts to new sqids alphabet")


def downgrade() -> None:
    """
    Revert sqids back to OLD alphabet.
    
    Process:
    1. Decode each public_sqid using NEW alphabet to get integer id
    2. Re-encode using OLD alphabet
    3. Update the public_sqid column
    """
    import os
    from sqids import Sqids
    
    # Get alphabets from environment
    old_alphabet = os.getenv("SQIDS_ALPHABET", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    new_alphabet = os.getenv("NEW_SQIDS_ALPHABET", old_alphabet)
    
    # Create Sqids instances
    sqids_old = Sqids(alphabet=old_alphabet, min_length=0)
    sqids_new = Sqids(alphabet=new_alphabet, min_length=0)
    
    # Get connection
    connection = op.get_bind()
    
    # Fetch all posts with their public_sqid and id
    result = connection.execute(text("SELECT id, public_sqid FROM posts WHERE public_sqid IS NOT NULL"))
    posts = result.fetchall()
    
    # Re-encode each post back to old alphabet
    updated_count = 0
    for post_id, new_sqid in posts:
        try:
            # Decode using new alphabet
            decoded = sqids_new.decode(new_sqid)
            if decoded and len(decoded) == 1:
                # Re-encode using old alphabet
                old_sqid = sqids_old.encode([decoded[0]])
                
                # Verify we got the same post_id
                if decoded[0] == post_id:
                    # Update the public_sqid
                    connection.execute(
                        text("UPDATE posts SET public_sqid = :old_sqid WHERE id = :id"),
                        {"old_sqid": old_sqid, "id": post_id}
                    )
                    updated_count += 1
                else:
                    print(f"Warning: Post {post_id} decoded to {decoded[0]}, skipping")
            else:
                print(f"Warning: Post {post_id} has invalid sqid {new_sqid}, skipping")
        except Exception as e:
            print(f"Error processing post {post_id} with sqid {new_sqid}: {e}")
    
    print(f"Reverted {updated_count} posts to old sqids alphabet")

