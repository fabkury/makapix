from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from .db import SessionLocal
from .models import (
    BadgeGrant,
    Comment,
    Follow,
    Playlist,
    Post,
    Reaction,
    ReputationHistory,
    User,
)

logger = logging.getLogger(__name__)


def ensure_seed_data() -> None:
    """
    Ensure seed data exists in the database (idempotent).
    
    Creates sample users, posts, comments, playlists, and relationships
    for development and testing purposes.
    """
    logger.info("ensure_seed_data: Starting...")
    try:
        logger.info("ensure_seed_data: Creating session...")
        with SessionLocal() as session:
            logger.info("ensure_seed_data: Session created, checking for existing data...")
            # Check if seed data already exists
            existing = session.scalar(select(User.id).limit(1))
            logger.info(f"ensure_seed_data: Existing data check result: {existing}")
            if existing:
                logger.debug("Seed data already present, skipping.")
                return

            logger.info("Creating seed data...")
        
            # ====================================================================
            # USERS
            # ====================================================================
        
            # Create admin user
            admin = User(
            id=uuid.uuid4(),
            handle="admin",
            display_name="Admin User",
            bio="Platform administrator",
            email="admin@makapix.club",
            reputation=1000,
            roles=["user", "moderator", "owner"],
        )
            session.add(admin)
            
            # Create moderator user
        moderator = User(
            id=uuid.uuid4(),
            handle="moderator",
            display_name="Mod User",
            bio="Community moderator keeping things friendly",
            email="mod@makapix.club",
            reputation=500,
            roles=["user", "moderator"],
        )
        session.add(moderator)
        
        # Create regular users
        alice = User(
            id=uuid.uuid4(),
            handle="alice",
            display_name="Alice Art",
            bio="Pixel artist | Retro game enthusiast | Coffee addict ☕",
            website="https://alice-art.example.com",
            reputation=150,
            roles=["user"],
        )
        session.add(alice)
        
        bob = User(
            id=uuid.uuid4(),
            handle="bob",
            display_name="Bob Pixel",
            bio="Creating tiny worlds one pixel at a time 🎨",
            reputation=80,
            roles=["user"],
        )
        session.add(bob)
        
        carol = User(
            id=uuid.uuid4(),
            handle="carol",
            display_name="Carol Creative",
            bio="Indie game dev & pixel art creator",
            website="https://carol.dev",
            reputation=200,
            roles=["user"],
        )
        session.add(carol)
        
        dave = User(
            id=uuid.uuid4(),
            handle="dave",
            display_name="Dave Designer",
            bio="Design first, pixels second",
            reputation=45,
            roles=["user"],
        )
        session.add(dave)
        
        # GitHub OAuth test users
        github_user = User(
            id=uuid.uuid4(),
            handle="githubuser",
            display_name="GitHub User",
            bio="Test user created via GitHub OAuth",
            github_user_id="12345",
            github_username="testuser",
            email="testuser@example.com",
            reputation=100,
            roles=["user"],
        )
        session.add(github_user)
        
        session.flush()  # Get IDs assigned
        
        # ====================================================================
        # BADGES
        # ====================================================================
        
        # Grant badges
        session.add(BadgeGrant(user_id=admin.id, badge="early-adopter"))
        session.add(BadgeGrant(user_id=moderator.id, badge="early-adopter"))
        session.add(BadgeGrant(user_id=moderator.id, badge="moderator"))
        session.add(BadgeGrant(user_id=alice.id, badge="early-adopter"))
        session.add(BadgeGrant(user_id=alice.id, badge="top-contributor"))
        session.add(BadgeGrant(user_id=carol.id, badge="top-contributor"))
        
        # ====================================================================
        # REPUTATION HISTORY
        # ====================================================================
        
        session.add(ReputationHistory(
            user_id=alice.id,
            delta=100,
            reason="Initial reputation bonus",
        ))
        session.add(ReputationHistory(
            user_id=alice.id,
            delta=50,
            reason="Quality post bonus",
        ))
        session.add(ReputationHistory(
            user_id=bob.id,
            delta=80,
            reason="Initial reputation bonus",
        ))
        session.add(ReputationHistory(
            user_id=carol.id,
            delta=200,
            reason="Top contributor bonus",
        ))
        
        # ====================================================================
        # FOLLOWS
        # ====================================================================
        
        # Alice follows Bob and Carol
        session.add(Follow(follower_id=alice.id, following_id=bob.id))
        session.add(Follow(follower_id=alice.id, following_id=carol.id))
        
        # Bob follows Alice
        session.add(Follow(follower_id=bob.id, following_id=alice.id))
        
        # Carol follows Alice and Bob
        session.add(Follow(follower_id=carol.id, following_id=alice.id))
        session.add(Follow(follower_id=carol.id, following_id=bob.id))
        
        # Dave follows everyone
        session.add(Follow(follower_id=dave.id, following_id=alice.id))
        session.add(Follow(follower_id=dave.id, following_id=bob.id))
        session.add(Follow(follower_id=dave.id, following_id=carol.id))
        
        # ====================================================================
        # POSTS
        # ====================================================================
        
        # Alice's posts
        alice_post1 = Post(
            id=uuid.uuid4(),
            owner_id=alice.id,
            kind="art",
            title="Sunset Over Pixel Mountains",
            description="A peaceful landscape scene with vibrant colors",
            hashtags=["landscape", "sunset", "mountains"],
            art_url="https://example.com/art/alice-sunset.png",
            canvas="64x64",
            file_kb=32,
            promoted=True,
            promoted_category="frontpage",
        )
        session.add(alice_post1)
        
        alice_post2 = Post(
            id=uuid.uuid4(),
            owner_id=alice.id,
            kind="art",
            title="Retro Space Ship",
            description="8-bit style spaceship for my game project",
            hashtags=["spaceship", "retro", "gamedev"],
            art_url="https://example.com/art/alice-spaceship.png",
            canvas="32x32",
            file_kb=18,
        )
        session.add(alice_post2)
        
        alice_post3 = Post(
            id=uuid.uuid4(),
            owner_id=alice.id,
            kind="art",
            title="Pixel Coffee Shop",
            description="Cozy little coffee shop interior ☕",
            hashtags=["interior", "coffee", "cozy"],
            art_url="https://example.com/art/alice-coffee.png",
            canvas="128x128",
            file_kb=85,
            promoted=True,
            promoted_category="editor-pick",
        )
        session.add(alice_post3)
        
        # Bob's posts
        bob_post1 = Post(
            id=uuid.uuid4(),
            owner_id=bob.id,
            kind="art",
            title="Tiny Forest Scene",
            description="Experimenting with green palettes",
            hashtags=["forest", "nature", "green"],
            art_url="https://example.com/art/bob-forest.png",
            canvas="64x64",
            file_kb=28,
        )
        session.add(bob_post1)
        
        bob_post2 = Post(
            id=uuid.uuid4(),
            owner_id=bob.id,
            kind="art",
            title="Pixel Character Pack",
            description="Character sprites for a platformer",
            hashtags=["character", "sprite", "gamedev"],
            art_url="https://example.com/art/bob-characters.png",
            canvas="32x32",
            file_kb=45,
        )
        session.add(bob_post2)
        
        # Carol's posts
        carol_post1 = Post(
            id=uuid.uuid4(),
            owner_id=carol.id,
            kind="art",
            title="Cyberpunk City Night",
            description="Neon-lit streets and rain reflections",
            hashtags=["cyberpunk", "city", "neon"],
            art_url="https://example.com/art/carol-cyberpunk.png",
            canvas="128x128",
            file_kb=120,
            promoted=True,
            promoted_category="weekly-pack",
        )
        session.add(carol_post1)
        
        carol_post2 = Post(
            id=uuid.uuid4(),
            owner_id=carol.id,
            kind="art",
            title="Underwater Cave",
            description="Exploring color gradients with water themes",
            hashtags=["underwater", "cave", "blue"],
            art_url="https://example.com/art/carol-underwater.png",
            canvas="64x64",
            file_kb=38,
        )
        session.add(carol_post2)
        
        # Dave's post
        dave_post1 = Post(
            id=uuid.uuid4(),
            owner_id=dave.id,
            kind="art",
            title="Minimalist House",
            description="Simple geometric shapes, clean design",
            hashtags=["minimalist", "architecture", "simple"],
            art_url="https://example.com/art/dave-house.png",
            canvas="32x32",
            file_kb=15,
        )
        session.add(dave_post1)
        
        session.flush()  # Get post IDs
        
        # ====================================================================
        # REACTIONS
        # ====================================================================
        
        # Reactions on Alice's sunset post
        session.add(Reaction(post_id=alice_post1.id, user_id=bob.id, emoji="❤️"))
        session.add(Reaction(post_id=alice_post1.id, user_id=carol.id, emoji="❤️"))
        session.add(Reaction(post_id=alice_post1.id, user_id=dave.id, emoji="😍"))
        session.add(Reaction(post_id=alice_post1.id, user_id=moderator.id, emoji="🔥"))
        
        # Reactions on Alice's coffee shop
        session.add(Reaction(post_id=alice_post3.id, user_id=bob.id, emoji="☕"))
        session.add(Reaction(post_id=alice_post3.id, user_id=carol.id, emoji="❤️"))
        session.add(Reaction(post_id=alice_post3.id, user_id=dave.id, emoji="☕"))
        
        # Reactions on Carol's cyberpunk post
        session.add(Reaction(post_id=carol_post1.id, user_id=alice.id, emoji="🔥"))
        session.add(Reaction(post_id=carol_post1.id, user_id=bob.id, emoji="😍"))
        session.add(Reaction(post_id=carol_post1.id, user_id=dave.id, emoji="🔥"))
        
        # Reactions on Bob's forest
        session.add(Reaction(post_id=bob_post1.id, user_id=alice.id, emoji="🌲"))
        session.add(Reaction(post_id=bob_post1.id, user_id=carol.id, emoji="❤️"))
        
        # ====================================================================
        # COMMENTS
        # ====================================================================
        
        # Comments on Alice's sunset post
        comment1 = Comment(
            id=uuid.uuid4(),
            post_id=alice_post1.id,
            author_id=bob.id,
            depth=0,
            body="This is absolutely stunning! Love the color palette 🌅",
        )
        session.add(comment1)
        session.flush()
        
        comment1_reply = Comment(
            id=uuid.uuid4(),
            post_id=alice_post1.id,
            author_id=alice.id,
            parent_id=comment1.id,
            depth=1,
            body="Thanks Bob! Spent a lot of time getting the gradient right 😊",
        )
        session.add(comment1_reply)
        
        comment2 = Comment(
            id=uuid.uuid4(),
            post_id=alice_post1.id,
            author_id=carol.id,
            depth=0,
            body="The atmospheric perspective is perfect. Great work!",
        )
        session.add(comment2)
        
        # Comments on Carol's cyberpunk post
        comment3 = Comment(
            id=uuid.uuid4(),
            post_id=carol_post1.id,
            author_id=alice.id,
            depth=0,
            body="Those neon reflections are incredible! How did you achieve that effect?",
        )
        session.add(comment3)
        session.flush()
        
        comment3_reply = Comment(
            id=uuid.uuid4(),
            post_id=carol_post1.id,
            author_id=carol.id,
            parent_id=comment3.id,
            depth=1,
            body="Thanks! I used a custom dithering pattern for the reflections. Happy to share the technique!",
        )
        session.add(comment3_reply)
        
        comment3_reply2 = Comment(
            id=uuid.uuid4(),
            post_id=carol_post1.id,
            author_id=alice.id,
            parent_id=comment3.id,
            depth=1,
            body="That would be awesome! Would love to learn more about your process.",
        )
        session.add(comment3_reply2)
        
        comment4 = Comment(
            id=uuid.uuid4(),
            post_id=carol_post1.id,
            author_id=bob.id,
            depth=0,
            body="Getting some serious Blade Runner vibes here 🌃",
        )
        session.add(comment4)
        
        # Comment on Bob's forest
        comment5 = Comment(
            id=uuid.uuid4(),
            post_id=bob_post1.id,
            author_id=alice.id,
            depth=0,
            body="Really nice use of different shades of green! 🌲",
        )
        session.add(comment5)
        
        # ====================================================================
        # PLAYLISTS
        # ====================================================================
        
        # Alice's playlist
        alice_playlist = Playlist(
            id=uuid.uuid4(),
            owner_id=alice.id,
            title="My Favorite Landscapes",
            description="Collection of landscape artworks that inspire me",
            post_ids=[alice_post1.id, bob_post1.id, carol_post2.id],
        )
        session.add(alice_playlist)
        
        # Carol's playlist
        carol_playlist = Playlist(
            id=uuid.uuid4(),
            owner_id=carol.id,
            title="Urban & Cyberpunk",
            description="City scenes and cyberpunk aesthetics",
            post_ids=[carol_post1.id, alice_post3.id],
        )
        session.add(carol_playlist)
        
        # Bob's playlist
        bob_playlist = Playlist(
            id=uuid.uuid4(),
            owner_id=bob.id,
            title="Game Dev Inspiration",
            description="Pixel art for game development projects",
            post_ids=[alice_post2.id, bob_post2.id, carol_post1.id],
        )
        session.add(bob_playlist)
        
        # ====================================================================
        # ANONYMOUS COMMENTS & REACTIONS
        # ====================================================================
        
        # Anonymous comments on Alice's coffee shop post
        anon_comment1 = Comment(
            id=uuid.uuid4(),
            post_id=alice_post3.id,
            author_id=None,  # Anonymous
            author_ip="192.168.1.100",  # Example IP
            depth=0,
            body="Amazing work! Love the attention to detail in the furniture.",
        )
        session.add(anon_comment1)
        session.flush()
        
        # Reply from another anonymous user
        anon_comment2 = Comment(
            id=uuid.uuid4(),
            post_id=alice_post3.id,
            author_id=None,  # Anonymous
            author_ip="192.168.1.101",  # Different IP
            parent_id=anon_comment1.id,
            depth=1,
            body="I agree! The pixel art style is perfect for this cozy vibe.",
        )
        session.add(anon_comment2)
        
        # Anonymous comment on Bob's forest post
        anon_comment3 = Comment(
            id=uuid.uuid4(),
            post_id=bob_post1.id,
            author_id=None,  # Anonymous
            author_ip="10.0.0.50",
            depth=0,
            body="Beautiful use of colors! Really captures the forest atmosphere.",
        )
        session.add(anon_comment3)
        
        # Anonymous comment on Carol's cyberpunk post
        anon_comment4 = Comment(
            id=uuid.uuid4(),
            post_id=carol_post1.id,
            author_id=None,  # Anonymous
            author_ip="172.16.0.10",
            depth=0,
            body="This is giving me all the cyberpunk vibes! Awesome work!",
        )
        session.add(anon_comment4)
        
        # Anonymous reactions on various posts
        # Multiple reactions from same IP (testing the 5 reaction limit)
        session.add(Reaction(post_id=alice_post1.id, user_id=None, user_ip="192.168.1.100", emoji="❤️"))
        session.add(Reaction(post_id=alice_post1.id, user_id=None, user_ip="192.168.1.100", emoji="👍"))
        session.add(Reaction(post_id=alice_post1.id, user_id=None, user_ip="192.168.1.100", emoji="🔥"))
        
        # Reactions from different anonymous users
        session.add(Reaction(post_id=alice_post3.id, user_id=None, user_ip="192.168.1.101", emoji="☕"))
        session.add(Reaction(post_id=alice_post3.id, user_id=None, user_ip="10.0.0.50", emoji="❤️"))
        
        session.add(Reaction(post_id=bob_post1.id, user_id=None, user_ip="172.16.0.10", emoji="🌲"))
        session.add(Reaction(post_id=bob_post1.id, user_id=None, user_ip="192.168.1.100", emoji="😍"))
        
        session.add(Reaction(post_id=carol_post1.id, user_id=None, user_ip="10.0.0.50", emoji="🔥"))
        session.add(Reaction(post_id=carol_post1.id, user_id=None, user_ip="172.16.0.10", emoji="😍"))
        
        # ====================================================================
        # COMMIT
        # ====================================================================
        
        session.commit()
        
        logger.info(f"Seed data created successfully:")
        logger.info(f"  - Users: 6 (1 owner, 1 moderator, 4 regular)")
        logger.info(f"  - Posts: 8")
        logger.info(f"  - Comments: 9 (with replies)")
        logger.info(f"  - Reactions: 14")
        logger.info(f"  - Follows: 7")
        logger.info(f"  - Playlists: 3")
        logger.info(f"  - Badges: 6")
    except Exception as e:
        logger.error(f"ensure_seed_data: Error occurred: {e}", exc_info=True)
        raise
    finally:
        logger.info("ensure_seed_data: Completed.")


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    ensure_seed_data()
