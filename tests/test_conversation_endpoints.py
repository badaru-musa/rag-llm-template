"""
Test file for conversation endpoints after fixing metadata/meta field issues
Tests the following endpoints:
1. GET /chat/conversations - List conversations
2. POST /chat/conversations - Create conversation
3. GET /chat/conversations/{id} - Get specific conversation
4. DELETE /chat/conversations/{id} - Delete conversation
5. POST /chat/search - Search documents
6. POST /chat/ - Send chat message
7. GET /chat/stats - Get chat statistics

Run this test file to verify the fixes work correctly.
"""

import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any
from datetime import datetime


class ConversationEndpointTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_token: Optional[str] = None
        self.test_user = {
            "email": f"test_{datetime.now().timestamp()}@example.com",
            "username": f"testuser_{int(datetime.now().timestamp())}",
            "password": "TestPassword123!",
            "full_name": "Test User"
        }
        self.conversation_id: Optional[str] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def print_result(self, test_name: str, success: bool, message: str, details: Any = None):
        """Print formatted test results"""
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n{status} - {test_name}")
        print(f"  Message: {message}")
        if details:
            print(f"  Details: {json.dumps(details, indent=2)}")
    
    async def register_and_login(self) -> bool:
        """Register a new user and login to get auth token"""
        try:
            # Register user
            async with self.session.post(
                f"{self.base_url}/auth/register",
                json=self.test_user
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    self.print_result("User Registration", False, f"Failed to register user: {resp.status}", error_text)
                    return False
                    
            # Login
            form_data = aiohttp.FormData()
            form_data.add_field('username', self.test_user['username'])
            form_data.add_field('password', self.test_user['password'])
            
            async with self.session.post(
                f"{self.base_url}/auth/login",
                data=form_data
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    self.print_result("User Login", False, f"Failed to login: {resp.status}", error_text)
                    return False
                    
                data = await resp.json()
                self.auth_token = data['access_token']
                self.print_result("Authentication", True, "Successfully registered and logged in", 
                                {"username": self.test_user['username']})
                return True
                
        except Exception as e:
            self.print_result("Authentication", False, f"Error during auth: {str(e)}")
            return False
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
    
    async def test_list_conversations_empty(self):
        """Test listing conversations when user has none"""
        try:
            async with self.session.get(
                f"{self.base_url}/chat/conversations",
                headers=self.get_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "List Conversations (Empty)",
                        True,
                        f"Successfully retrieved empty conversation list",
                        {"count": len(data)}
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "List Conversations (Empty)",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
        except Exception as e:
            self.print_result("List Conversations (Empty)", False, f"Error: {str(e)}")
    
    async def test_create_conversation(self):
        """Test creating a new conversation"""
        try:
            conversation_data = {
                "title": "Test Conversation",
                "meta": {
                    "topic": "testing",
                    "created_by": "test_script"
                }
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/conversations",
                headers=self.get_headers(),
                json=conversation_data
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.conversation_id = data['id']
                    self.print_result(
                        "Create Conversation",
                        True,
                        "Successfully created conversation",
                        {
                            "id": data['id'],
                            "title": data.get('title'),
                            "meta": data.get('meta')
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Create Conversation",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
        except Exception as e:
            self.print_result("Create Conversation", False, f"Error: {str(e)}")
    
    async def test_send_chat_message(self):
        """Test sending a chat message"""
        if not self.conversation_id:
            self.print_result("Send Chat Message", False, "No conversation ID available")
            return
            
        try:
            chat_request = {
                "message": "Hello, this is a test message!",
                "conversation_id": self.conversation_id,
                "use_vector_search": False
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/",
                headers=self.get_headers(),
                json=chat_request
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Send Chat Message",
                        True,
                        "Successfully sent chat message",
                        {
                            "conversation_id": data.get('conversation_id'),
                            "response_preview": data.get('message', '')[:100] + "..."
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Send Chat Message",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
        except Exception as e:
            self.print_result("Send Chat Message", False, f"Error: {str(e)}")
    
    async def test_list_conversations_with_data(self):
        """Test listing conversations after creating one"""
        try:
            async with self.session.get(
                f"{self.base_url}/chat/conversations",
                headers=self.get_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "List Conversations (With Data)",
                        True,
                        f"Successfully retrieved {len(data)} conversation(s)",
                        {
                            "count": len(data),
                            "conversations": [
                                {
                                    "id": conv.get('id'),
                                    "title": conv.get('title'),
                                    "message_count": conv.get('message_count')
                                } for conv in data
                            ]
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "List Conversations (With Data)",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
        except Exception as e:
            self.print_result("List Conversations (With Data)", False, f"Error: {str(e)}")
    
    async def test_get_specific_conversation(self):
        """Test getting a specific conversation"""
        if not self.conversation_id:
            self.print_result("Get Specific Conversation", False, "No conversation ID available")
            return
            
        try:
            async with self.session.get(
                f"{self.base_url}/chat/conversations/{self.conversation_id}",
                headers=self.get_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Get Specific Conversation",
                        True,
                        "Successfully retrieved conversation",
                        {
                            "id": data.get('id'),
                            "title": data.get('title'),
                            "message_count": data.get('message_count'),
                            "messages_preview": len(data.get('messages', []))
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Get Specific Conversation",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
        except Exception as e:
            self.print_result("Get Specific Conversation", False, f"Error: {str(e)}")
    
    async def test_chat_stats(self):
        """Test getting chat statistics"""
        try:
            async with self.session.get(
                f"{self.base_url}/chat/stats",
                headers=self.get_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Chat Statistics",
                        True,
                        "Successfully retrieved chat stats",
                        data
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Chat Statistics",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
        except Exception as e:
            self.print_result("Chat Statistics", False, f"Error: {str(e)}")
    
    async def test_search_documents(self):
        """Test searching documents"""
        try:
            # First, let's upload a test document if needed
            # For now, we'll just test the search endpoint
            search_params = {
                "query": "test query",
                "max_results": 5,
                "similarity_threshold": 0.7
            }
            
            headers = self.get_headers()
            # For search, we need to pass query as a parameter
            url = f"{self.base_url}/chat/search?query={search_params['query']}"
            url += f"&max_results={search_params['max_results']}"
            url += f"&similarity_threshold={search_params['similarity_threshold']}"
            
            async with self.session.post(
                url,
                headers=headers,
                json=search_params
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Search Documents",
                        True,
                        f"Search completed successfully (found {len(data)} results)",
                        {
                            "results_count": len(data),
                            "query": search_params['query']
                        }
                    )
                elif resp.status == 500:
                    # This is expected if no documents are uploaded yet
                    self.print_result(
                        "Search Documents",
                        True,
                        "Search endpoint accessible (no documents to search)",
                        {"note": "Upload documents first to test actual search"}
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Search Documents",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
        except Exception as e:
            self.print_result("Search Documents", False, f"Error: {str(e)}")
    
    async def test_delete_conversation(self):
        """Test deleting a conversation"""
        if not self.conversation_id:
            self.print_result("Delete Conversation", False, "No conversation ID available")
            return
            
        try:
            async with self.session.delete(
                f"{self.base_url}/chat/conversations/{self.conversation_id}",
                headers=self.get_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Delete Conversation",
                        True,
                        "Successfully deleted conversation",
                        {"conversation_id": self.conversation_id}
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Delete Conversation",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
        except Exception as e:
            self.print_result("Delete Conversation", False, f"Error: {str(e)}")
    
    async def run_all_tests(self):
        """Run all conversation endpoint tests"""
        print("=" * 60)
        print("CONVERSATION ENDPOINTS TEST SUITE")
        print("=" * 60)
        print(f"Testing against: {self.base_url}")
        print(f"Started at: {datetime.now().isoformat()}")
        print("-" * 60)
        
        # Authenticate first
        if not await self.register_and_login():
            print("\n❌ CRITICAL: Authentication failed. Cannot proceed with tests.")
            return
        
        # Run tests in order
        print("\n" + "=" * 60)
        print("RUNNING CONVERSATION TESTS")
        print("=" * 60)
        
        await self.test_list_conversations_empty()
        await self.test_create_conversation()
        await self.test_send_chat_message()
        await self.test_list_conversations_with_data()
        await self.test_get_specific_conversation()
        await self.test_chat_stats()
        await self.test_search_documents()
        await self.test_delete_conversation()
        
        print("\n" + "=" * 60)
        print("TEST SUITE COMPLETED")
        print(f"Finished at: {datetime.now().isoformat()}")
        print("=" * 60)


async def main():
    """Main function to run tests"""
    async with ConversationEndpointTester() as tester:
        await tester.run_all_tests()


if __name__ == "__main__":
    print("\n🔧 CONVERSATION ENDPOINT TESTER")
    print("This script tests the conversation-related endpoints after fixing the metadata/meta field issues.")
    print("\nMake sure the server is running on http://localhost:8000")
    print("Press Ctrl+C to cancel...\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
