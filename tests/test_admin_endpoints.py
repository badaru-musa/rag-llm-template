"""
Test file for admin user management endpoints
Tests the following admin-only endpoints:
1. POST /admin/users - Create new user
2. DELETE /admin/users/{id} - Delete user
3. PUT /admin/users/{id}/role - Update user role
4. PUT /admin/users/{id}/status - Enable/disable user
5. GET /admin/users - List all users
6. GET /admin/users/{id} - Get user details
7. GET /admin/users/{id}/stats - Get user statistics
8. GET /admin/stats/overview - Get system overview

Run this test to verify admin functionality works correctly.
"""

import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any
from datetime import datetime
import random
import string


class AdminEndpointTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.admin_token: Optional[str] = None
        self.user_token: Optional[str] = None
        
        # Generate unique credentials for test admin
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.admin_user = {
            "email": f"admin_{unique_id}@example.com",
            "username": f"admin_{unique_id}",
            "password": "AdminPassword123!",
            "full_name": "Test Admin User",
            "role": "admin"
        }
        
        # Regular user for testing
        self.regular_user = {
            "email": f"user_{unique_id}@example.com",
            "username": f"user_{unique_id}",
            "password": "UserPassword123!",
            "full_name": "Test Regular User",
            "role": "user"
        }
        
        self.created_user_ids = []
        
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
            if isinstance(details, str):
                print(f"  Details: {details}")
            else:
                print(f"  Details: {json.dumps(details, indent=2, default=str)}")
    
    async def setup_admin_user(self) -> bool:
        """Create and authenticate an admin user for testing"""
        try:
            # First, we need to create an initial admin user
            # This assumes there's already an admin in the system or this is the first user
            
            # Try to register as admin (this might fail if system already has users)
            async with self.session.post(
                f"{self.base_url}/auth/register",
                json=self.admin_user
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # First user might automatically be admin in some systems
                    self.print_result("Admin Registration", True, "Admin user registered", 
                                    {"username": self.admin_user['username']})
                else:
                    # Admin might already exist, try to login with default admin
                    self.print_result("Admin Registration", False, 
                                    "Could not register admin (may already exist)")
            
            # Login as admin
            form_data = aiohttp.FormData()
            form_data.add_field('username', self.admin_user['username'])
            form_data.add_field('password', self.admin_user['password'])
            
            async with self.session.post(
                f"{self.base_url}/auth/login",
                data=form_data
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.admin_token = data['access_token']
                    self.print_result("Admin Login", True, "Successfully logged in as admin")
                    
                    # Verify admin role
                    headers = {"Authorization": f"Bearer {self.admin_token}"}
                    async with self.session.get(
                        f"{self.base_url}/auth/me",
                        headers=headers
                    ) as verify_resp:
                        if verify_resp.status == 200:
                            user_data = await verify_resp.json()
                            if user_data.get('role') != 'admin':
                                # Try to make the user admin if not already
                                print(f"  Note: User role is {user_data.get('role')}, not admin")
                                return False
                    return True
                else:
                    self.print_result("Admin Login", False, "Failed to login as admin")
                    return False
                    
        except Exception as e:
            self.print_result("Admin Setup", False, f"Error: {str(e)}")
            return False
    
    def get_admin_headers(self) -> Dict[str, str]:
        """Get headers with admin authentication"""
        return {
            "Authorization": f"Bearer {self.admin_token}",
            "Content-Type": "application/json"
        }
    
    def get_user_headers(self) -> Dict[str, str]:
        """Get headers with regular user authentication"""
        return {
            "Authorization": f"Bearer {self.user_token}",
            "Content-Type": "application/json"
        }
    
    async def test_create_user(self):
        """Test creating a new user as admin"""
        try:
            # Generate unique user data
            unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            new_user = {
                "email": f"created_{unique_id}@example.com",
                "username": f"created_{unique_id}",
                "password": "CreatedUser123!",
                "full_name": "Admin Created User",
                "role": "user"
            }
            
            async with self.session.post(
                f"{self.base_url}/admin/users",
                headers=self.get_admin_headers(),
                json=new_user
            ) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    self.created_user_ids.append(data['id'])
                    self.print_result(
                        "Create User (Admin)",
                        True,
                        "Successfully created user via admin endpoint",
                        {
                            "user_id": data['id'],
                            "username": data['username'],
                            "role": data['role']
                        }
                    )
                    return data['id']
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Create User (Admin)",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    return None
                    
        except Exception as e:
            self.print_result("Create User (Admin)", False, f"Error: {str(e)}")
            return None
    
    async def test_list_users(self):
        """Test listing all users as admin"""
        try:
            async with self.session.get(
                f"{self.base_url}/admin/users",
                headers=self.get_admin_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "List All Users",
                        True,
                        f"Successfully retrieved {len(data)} users",
                        {
                            "total_users": len(data),
                            "first_3_users": [
                                {"id": u.get('id'), "username": u.get('username'), "role": u.get('role')}
                                for u in data[:3]
                            ]
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "List All Users",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("List All Users", False, f"Error: {str(e)}")
    
    async def test_get_user_details(self, user_id: int):
        """Test getting user details as admin"""
        if not user_id:
            self.print_result("Get User Details", False, "No user ID provided")
            return
            
        try:
            async with self.session.get(
                f"{self.base_url}/admin/users/{user_id}",
                headers=self.get_admin_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Get User Details",
                        True,
                        f"Successfully retrieved details for user {user_id}",
                        {
                            "username": data.get('username'),
                            "email": data.get('email'),
                            "role": data.get('role'),
                            "is_active": data.get('is_active')
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Get User Details",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("Get User Details", False, f"Error: {str(e)}")
    
    async def test_update_user_role(self, user_id: int):
        """Test updating user role as admin"""
        if not user_id:
            self.print_result("Update User Role", False, "No user ID provided")
            return
            
        try:
            # Promote user to admin
            async with self.session.put(
                f"{self.base_url}/admin/users/{user_id}/role?new_role=admin",
                headers=self.get_admin_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Update User Role (Promote)",
                        True,
                        f"Successfully promoted user {user_id} to admin",
                        {"new_role": data.get('role')}
                    )
                    
                    # Demote back to user
                    async with self.session.put(
                        f"{self.base_url}/admin/users/{user_id}/role?new_role=user",
                        headers=self.get_admin_headers()
                    ) as demote_resp:
                        if demote_resp.status == 200:
                            demote_data = await demote_resp.json()
                            self.print_result(
                                "Update User Role (Demote)",
                                True,
                                f"Successfully demoted user {user_id} back to user",
                                {"new_role": demote_data.get('role')}
                            )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Update User Role",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("Update User Role", False, f"Error: {str(e)}")
    
    async def test_update_user_status(self, user_id: int):
        """Test enabling/disabling user as admin"""
        if not user_id:
            self.print_result("Update User Status", False, "No user ID provided")
            return
            
        try:
            # Disable user
            async with self.session.put(
                f"{self.base_url}/admin/users/{user_id}/status?is_active=false",
                headers=self.get_admin_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Update User Status (Disable)",
                        True,
                        f"Successfully disabled user {user_id}",
                        {"is_active": data.get('is_active')}
                    )
                    
                    # Re-enable user
                    async with self.session.put(
                        f"{self.base_url}/admin/users/{user_id}/status?is_active=true",
                        headers=self.get_admin_headers()
                    ) as enable_resp:
                        if enable_resp.status == 200:
                            enable_data = await enable_resp.json()
                            self.print_result(
                                "Update User Status (Enable)",
                                True,
                                f"Successfully re-enabled user {user_id}",
                                {"is_active": enable_data.get('is_active')}
                            )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Update User Status",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("Update User Status", False, f"Error: {str(e)}")
    
    async def test_get_user_stats(self, user_id: int):
        """Test getting user statistics as admin"""
        if not user_id:
            self.print_result("Get User Statistics", False, "No user ID provided")
            return
            
        try:
            async with self.session.get(
                f"{self.base_url}/admin/users/{user_id}/stats",
                headers=self.get_admin_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Get User Statistics",
                        True,
                        f"Successfully retrieved statistics for user {user_id}",
                        {
                            "documents": data.get('statistics', {}).get('documents', {}),
                            "conversations": data.get('statistics', {}).get('conversations', {}),
                            "storage_mb": data.get('statistics', {}).get('storage', {}).get('total_size_mb')
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Get User Statistics",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("Get User Statistics", False, f"Error: {str(e)}")
    
    async def test_system_overview(self):
        """Test getting system overview as admin"""
        try:
            async with self.session.get(
                f"{self.base_url}/admin/stats/overview",
                headers=self.get_admin_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "System Overview",
                        True,
                        "Successfully retrieved system statistics",
                        {
                            "total_users": data.get('users', {}).get('total'),
                            "active_users": data.get('users', {}).get('active'),
                            "total_documents": data.get('documents', {}).get('total'),
                            "total_conversations": data.get('conversations', {}).get('total')
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "System Overview",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("System Overview", False, f"Error: {str(e)}")
    
    async def test_delete_user(self, user_id: int):
        """Test deleting a user as admin"""
        if not user_id:
            self.print_result("Delete User", False, "No user ID provided")
            return
            
        try:
            async with self.session.delete(
                f"{self.base_url}/admin/users/{user_id}?cascade=true",
                headers=self.get_admin_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Delete User",
                        True,
                        f"Successfully deleted user {user_id}",
                        data
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Delete User",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("Delete User", False, f"Error: {str(e)}")
    
    async def test_access_control(self):
        """Test that regular users cannot access admin endpoints"""
        try:
            # Create and login as regular user
            unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            regular_user = {
                "email": f"regular_{unique_id}@example.com",
                "username": f"regular_{unique_id}",
                "password": "RegularUser123!",
                "full_name": "Regular User"
            }
            
            # Register regular user
            async with self.session.post(
                f"{self.base_url}/auth/register",
                json=regular_user
            ) as resp:
                if resp.status != 200:
                    self.print_result("Access Control Setup", False, "Failed to create regular user")
                    return
            
            # Login as regular user
            form_data = aiohttp.FormData()
            form_data.add_field('username', regular_user['username'])
            form_data.add_field('password', regular_user['password'])
            
            async with self.session.post(
                f"{self.base_url}/auth/login",
                data=form_data
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    user_token = data['access_token']
                else:
                    self.print_result("Access Control Setup", False, "Failed to login as regular user")
                    return
            
            # Try to access admin endpoint as regular user
            headers = {"Authorization": f"Bearer {user_token}"}
            async with self.session.get(
                f"{self.base_url}/admin/users",
                headers=headers
            ) as resp:
                if resp.status == 403:
                    self.print_result(
                        "Access Control",
                        True,
                        "Regular user correctly denied access to admin endpoint",
                        {"status_code": resp.status}
                    )
                else:
                    self.print_result(
                        "Access Control",
                        False,
                        f"Regular user got unexpected status {resp.status} (expected 403)",
                        await resp.text()
                    )
                    
        except Exception as e:
            self.print_result("Access Control", False, f"Error: {str(e)}")
    
    async def run_all_tests(self):
        """Run all admin endpoint tests"""
        print("=" * 60)
        print("ADMIN ENDPOINTS TEST SUITE")
        print("=" * 60)
        print(f"Testing against: {self.base_url}")
        print(f"Started at: {datetime.now().isoformat()}")
        print("-" * 60)
        
        # Setup admin user
        if not await self.setup_admin_user():
            print("\n❌ CRITICAL: Failed to setup admin user. Cannot proceed with tests.")
            print("\nNote: You may need to manually create an admin user first.")
            print("Or modify the first registered user to have admin role in the database.")
            return
        
        # Run tests
        print("\n" + "=" * 60)
        print("RUNNING ADMIN TESTS")
        print("=" * 60)
        
        # Test creating users
        created_user_id = await self.test_create_user()
        
        # Test listing users
        await self.test_list_users()
        
        # Test user details
        if created_user_id:
            await self.test_get_user_details(created_user_id)
            await self.test_update_user_role(created_user_id)
            await self.test_update_user_status(created_user_id)
            await self.test_get_user_stats(created_user_id)
        
        # Test system overview
        await self.test_system_overview()
        
        # Test access control
        await self.test_access_control()
        
        # Clean up - delete created user
        if created_user_id:
            await self.test_delete_user(created_user_id)
        
        print("\n" + "=" * 60)
        print("TEST SUITE COMPLETED")
        print(f"Finished at: {datetime.now().isoformat()}")
        print("=" * 60)


async def main():
    """Main function to run tests"""
    async with AdminEndpointTester() as tester:
        await tester.run_all_tests()


if __name__ == "__main__":
    print("\n👤 ADMIN ENDPOINTS TESTER")
    print("This script tests the admin user management endpoints.")
    print("\n⚠️  IMPORTANT: You need an admin user to run these tests.")
    print("If this is a fresh installation, the first registered user")
    print("might need to be manually promoted to admin in the database.")
    print("\nMake sure the server is running on http://localhost:8000")
    print("Press Ctrl+C to cancel...\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
