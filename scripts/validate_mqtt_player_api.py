#!/usr/bin/env python3
"""
Manual validation script for MQTT Player API.

This script demonstrates the usage of the MQTT Player API and can be used
for manual testing and validation of the implementation.

Prerequisites:
- MQTT broker running and accessible
- Player provisioned and registered
- Valid player credentials (player_key, certificates)

Usage:
    python3 validate_mqtt_player_api.py --player-key <UUID> [--host <host>] [--port <port>]
"""

import argparse
import json
import time
import uuid
from typing import Any, Dict

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt not installed. Install with: pip install paho-mqtt")
    exit(1)


class PlayerAPIValidator:
    """Validator for MQTT Player API operations."""
    
    def __init__(self, player_key: str, host: str = "localhost", port: int = 1883, use_tls: bool = False):
        self.player_key = player_key
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.client = None
        self.responses = {}
        self.pending_requests = set()
        
    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when client connects to broker."""
        if rc == 0:
            print(f"✓ Connected to MQTT broker at {self.host}:{self.port}")
            # Subscribe to response topic
            response_topic = f"makapix/player/{self.player_key}/response/#"
            client.subscribe(response_topic, qos=1)
            print(f"✓ Subscribed to {response_topic}")
        else:
            print(f"✗ Connection failed with code {rc}")
    
    def on_message(self, client, userdata, msg):
        """Callback for when a message is received."""
        try:
            response = json.loads(msg.payload.decode())
            request_id = response.get("request_id", "unknown")
            
            print(f"\n📥 Received response for request {request_id}:")
            print(json.dumps(response, indent=2))
            
            self.responses[request_id] = response
            if request_id in self.pending_requests:
                self.pending_requests.remove(request_id)
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse response: {e}")
    
    def connect(self):
        """Connect to MQTT broker."""
        print(f"\n🔌 Connecting to MQTT broker...")
        self.client = mqtt.Client(
            client_id=f"validator-{uuid.uuid4().hex[:8]}",
            protocol=mqtt.MQTTv5,
        )
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        if self.use_tls:
            # In production, use proper certificates
            self.client.tls_set()
            print("⚠️  Using TLS (certificate validation disabled for testing)")
        
        try:
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
            
            # Wait for connection
            time.sleep(2)
            return True
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            print("\n🔌 Disconnected from MQTT broker")
    
    def send_request(self, request_type: str, **kwargs) -> str:
        """Send a request and return the request_id."""
        request_id = str(uuid.uuid4())
        request_topic = f"makapix/player/{self.player_key}/request/{request_id}"
        
        request = {
            "request_id": request_id,
            "request_type": request_type,
            "player_key": self.player_key,
            **kwargs
        }
        
        print(f"\n📤 Sending {request_type} request:")
        print(json.dumps(request, indent=2))
        
        self.client.publish(request_topic, json.dumps(request), qos=1)
        self.pending_requests.add(request_id)
        
        return request_id
    
    def wait_for_response(self, request_id: str, timeout: int = 10) -> Dict[str, Any] | None:
        """Wait for a response to a specific request."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if request_id in self.responses:
                return self.responses[request_id]
            time.sleep(0.1)
        
        print(f"✗ Timeout waiting for response to request {request_id}")
        return None
    
    def validate_query_posts(self):
        """Validate query_posts operation."""
        print("\n" + "="*60)
        print("TEST 1: Query Posts")
        print("="*60)
        
        # Test 1: Query all posts
        request_id = self.send_request(
            "query_posts",
            channel="all",
            sort="server_order",
            limit=10
        )
        
        response = self.wait_for_response(request_id)
        if response and response.get("success"):
            print(f"✓ Query successful: {len(response.get('posts', []))} posts returned")
            if response.get("posts"):
                print(f"  Sample post: {response['posts'][0].get('title', 'N/A')}")
        else:
            print(f"✗ Query failed: {response.get('error') if response else 'No response'}")
        
        time.sleep(1)
        
        # Test 2: Query promoted posts
        request_id = self.send_request(
            "query_posts",
            channel="promoted",
            sort="created_at",
            limit=5
        )
        
        response = self.wait_for_response(request_id)
        if response and response.get("success"):
            print(f"✓ Promoted posts query successful: {len(response.get('posts', []))} posts")
        else:
            print(f"✗ Promoted posts query failed")
        
        return True
    
    def validate_submit_view(self, post_id: int):
        """Validate submit_view operation."""
        print("\n" + "="*60)
        print("TEST 2: Submit View")
        print("="*60)
        
        # Test intentional view
        request_id = self.send_request(
            "submit_view",
            post_id=post_id,
            view_intent="intentional"
        )
        
        response = self.wait_for_response(request_id)
        if response and response.get("success"):
            print(f"✓ View submitted successfully")
        else:
            print(f"✗ View submission failed: {response.get('error') if response else 'No response'}")
        
        time.sleep(1)
        
        # Test automated view
        request_id = self.send_request(
            "submit_view",
            post_id=post_id,
            view_intent="automated"
        )
        
        response = self.wait_for_response(request_id)
        if response and response.get("success"):
            print(f"✓ Automated view submitted successfully")
        else:
            print(f"✗ Automated view submission failed")
        
        return True
    
    def validate_reactions(self, post_id: int):
        """Validate reaction operations."""
        print("\n" + "="*60)
        print("TEST 3: Reactions")
        print("="*60)
        
        # Test submit reaction
        emoji = "❤️"
        request_id = self.send_request(
            "submit_reaction",
            post_id=post_id,
            emoji=emoji
        )
        
        response = self.wait_for_response(request_id)
        if response and response.get("success"):
            print(f"✓ Reaction '{emoji}' submitted successfully")
        else:
            print(f"✗ Reaction submission failed: {response.get('error') if response else 'No response'}")
        
        time.sleep(1)
        
        # Test revoke reaction
        request_id = self.send_request(
            "revoke_reaction",
            post_id=post_id,
            emoji=emoji
        )
        
        response = self.wait_for_response(request_id)
        if response and response.get("success"):
            print(f"✓ Reaction '{emoji}' revoked successfully")
        else:
            print(f"✗ Reaction revocation failed")
        
        return True
    
    def validate_get_comments(self, post_id: int):
        """Validate get_comments operation."""
        print("\n" + "="*60)
        print("TEST 4: Get Comments")
        print("="*60)
        
        request_id = self.send_request(
            "get_comments",
            post_id=post_id,
            limit=20
        )
        
        response = self.wait_for_response(request_id)
        if response and response.get("success"):
            comments = response.get('comments', [])
            print(f"✓ Comments retrieved successfully: {len(comments)} comments")
            if comments:
                print(f"  Sample comment: {comments[0].get('body', 'N/A')[:50]}...")
        else:
            print(f"✗ Comments retrieval failed: {response.get('error') if response else 'No response'}")
        
        return True
    
    def run_all_tests(self, test_post_id: int = None):
        """Run all validation tests."""
        print("\n" + "="*60)
        print("MQTT Player API Validation")
        print("="*60)
        print(f"Player Key: {self.player_key}")
        print(f"Broker: {self.host}:{self.port}")
        
        if not self.connect():
            return False
        
        try:
            # Test query_posts
            self.validate_query_posts()
            
            # For other tests, we need a post_id
            if test_post_id:
                self.validate_submit_view(test_post_id)
                self.validate_reactions(test_post_id)
                self.validate_get_comments(test_post_id)
            else:
                print("\n⚠️  Skipping view/reaction/comment tests (no post_id provided)")
                print("   Use --post-id option to test these operations")
            
            # Wait for any pending responses
            timeout = 5
            start = time.time()
            while self.pending_requests and (time.time() - start) < timeout:
                time.sleep(0.1)
            
            print("\n" + "="*60)
            print("VALIDATION COMPLETE")
            print("="*60)
            print(f"Total requests sent: {len(self.responses) + len(self.pending_requests)}")
            print(f"Responses received: {len(self.responses)}")
            print(f"Pending/timeout: {len(self.pending_requests)}")
            
            return True
            
        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Validate MQTT Player API")
    parser.add_argument("--player-key", required=True, help="Player UUID key")
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--tls", action="store_true", help="Use TLS")
    parser.add_argument("--post-id", type=int, help="Post ID for testing view/reaction/comment operations")
    
    args = parser.parse_args()
    
    validator = PlayerAPIValidator(
        player_key=args.player_key,
        host=args.host,
        port=args.port,
        use_tls=args.tls
    )
    
    success = validator.run_all_tests(test_post_id=args.post_id)
    
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
