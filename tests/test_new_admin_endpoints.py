"""
Test file for new admin endpoints: role creation and document permissions.

This test file validates the new admin functionality added to the project:
1. Admin role creation endpoint
2. Document permission management endpoints

Usage:
    python test_new_admin_endpoints.py

Prerequisites:
    - The application should be running (python app/main.py or uvicorn app.main:app)
    - Admin user account with proper credentials
    - At least one test document uploaded by the admin
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "http://localhost:8000"
ADMIN_USERNAME = "admin"  # Update with your admin username
ADMIN_PASSWORD = "admin123"  # Update with your admin password


class AdminEndpointTester:
    """Test class for admin endpoints"""
    
    def __init__(self, base_url: str, admin_username: str, admin_password: str):
        self.base_url = base_url.rstrip('/')
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.admin_token = None
        self.session = requests.Session()
        
    def authenticate_admin(self) -> bool:
        """Authenticate admin user and get access token"""
        print("🔑 Authenticating admin user...")
        
        try:
            # Login to get access token
            login_data = {
                "username": self.admin_username,
                "password": self.admin_password
            }
            
            response = self.session.post(
                f"{self.base_url}/auth/login",
                data=login_data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.admin_token = token_data["access_token"]
                
                # Set authorization header for future requests
                self.session.headers.update({
                    "Authorization": f"Bearer {self.admin_token}",
                    "Content-Type": "application/json"
                })
                
                print("✅ Admin authentication successful")
                return True
            else:
                print(f"❌ Admin authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error during admin authentication: {str(e)}")
            return False
    
    def test_health_check(self) -> bool:
        """Test basic health check"""
        print("\n🏥 Testing health check...")
        
        try:
            response = self.session.get(f"{self.base_url}/health")
            
            if response.status_code == 200:
                print("✅ Health check passed")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error during health check: {str(e)}")
            return False
    
    def test_create_role(self) -> Optional[Dict[str, Any]]:
        """Test creating a new role"""
        print("\n👥 Testing role creation...")
        
        try:
            role_data = {
                "name": f"test_role_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "description": "Test role created by automated test script",
                "permissions": {
                    "can_read_documents": True,
                    "can_create_documents": False,
                    "can_delete_documents": False,
                    "can_manage_users": False
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/admin/roles",
                json=role_data
            )
            
            if response.status_code == 201:
                created_role = response.json()
                print(f"✅ Role created successfully: {created_role['name']} (ID: {created_role['id']})")
                return created_role
            else:
                print(f"❌ Role creation failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error during role creation: {str(e)}")
            return None
    
    def test_list_roles(self) -> bool:
        """Test listing all roles"""
        print("\n📋 Testing role listing...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/roles")
            
            if response.status_code == 200:
                roles = response.json()
                print(f"✅ Retrieved {len(roles)} roles")
                
                # Display first few roles
                for role in roles[:3]:
                    print(f"   - {role['name']}: {role.get('description', 'No description')}")
                
                return True
            else:
                print(f"❌ Role listing failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error during role listing: {str(e)}")
            return False
    
    def get_test_document_id(self) -> Optional[int]:
        """Get a test document ID for permission testing"""
        print("\n📄 Looking for test documents...")
        
        try:
            response = self.session.get(f"{self.base_url}/documents/")
            
            if response.status_code == 200:
                documents = response.json()
                if documents:
                    doc_id = documents[0]["id"]
                    print(f"✅ Using document ID {doc_id} for permission tests")
                    return doc_id
                else:
                    print("⚠️  No documents found. Creating a test document...")
                    return self.create_test_document()
            else:
                print(f"❌ Failed to get documents: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting test document: {str(e)}")
            return None
    
    def create_test_document(self) -> Optional[int]:
        """Create a test document for permission testing"""
        try:
            # Create a simple text file for testing
            test_content = "This is a test document for permission testing."
            
            files = {
                "file": ("test_permissions.txt", test_content, "text/plain")
            }
            
            # Remove Content-Type header for file upload
            headers = {key: val for key, val in self.session.headers.items() 
                      if key.lower() != "content-type"}
            
            response = requests.post(
                f"{self.base_url}/documents/upload",
                files=files,
                headers=headers
            )
            
            if response.status_code == 201:
                document = response.json()
                doc_id = document["document_id"]
                print(f"✅ Test document created with ID {doc_id}")
                return doc_id
            else:
                print(f"❌ Failed to create test document: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating test document: {str(e)}")
            return None
    
    def test_create_document_permission(self, document_id: int, role_id: int) -> Optional[Dict[str, Any]]:
        """Test creating document permission for a role"""
        print(f"\n🔐 Testing document permission creation for document {document_id}...")
        
        try:
            permission_data = {
                "document_id": document_id,
                "role_id": role_id,
                "can_read": True,
                "can_write": False,
                "can_delete": False,
                "can_share": False,
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
            }
            
            response = self.session.post(
                f"{self.base_url}/admin/documents/{document_id}/permissions",
                json=permission_data
            )
            
            if response.status_code == 201:
                permission = response.json()
                print(f"✅ Document permission created successfully (ID: {permission['id']})")
                return permission
            else:
                print(f"❌ Document permission creation failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error during document permission creation: {str(e)}")
            return None
    
    def test_list_document_permissions(self, document_id: int) -> bool:
        """Test listing document permissions"""
        print(f"\n📋 Testing document permissions listing for document {document_id}...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/documents/{document_id}/permissions")
            
            if response.status_code == 200:
                permissions = response.json()
                print(f"✅ Retrieved {len(permissions)} permissions for document {document_id}")
                
                for perm in permissions:
                    target = f"user {perm['user_id']}" if perm['user_id'] else f"role {perm['role_id']}"
                    perms = []
                    if perm['can_read']: perms.append('read')
                    if perm['can_write']: perms.append('write')
                    if perm['can_delete']: perms.append('delete')
                    if perm['can_share']: perms.append('share')
                    print(f"   - {target}: {', '.join(perms) if perms else 'no permissions'}")
                
                return True
            else:
                print(f"❌ Document permissions listing failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error during document permissions listing: {str(e)}")
            return False
    
    def test_revoke_document_permission(self, document_id: int, permission_id: int) -> bool:
        """Test revoking document permission"""
        print(f"\n🚫 Testing document permission revocation...")
        
        try:
            response = self.session.delete(
                f"{self.base_url}/admin/documents/{document_id}/permissions/{permission_id}"
            )
            
            if response.status_code == 200:
                print(f"✅ Document permission revoked successfully")
                return True
            else:
                print(f"❌ Document permission revocation failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error during document permission revocation: {str(e)}")
            return False
    
    def test_debug_endpoints(self) -> bool:
        """Test existing debug endpoints to ensure they still work"""
        print("\n🐛 Testing existing debug endpoints...")
        
        try:
            # Test vector store stats
            response = self.session.get(f"{self.base_url}/debug/vector-store/stats")
            
            if response.status_code == 200:
                print("✅ Debug vector store stats endpoint working")
            else:
                print(f"❌ Debug vector store stats failed: {response.status_code}")
            
            # Test vector search
            search_response = self.session.post(
                f"{self.base_url}/debug/vector-store/test-search?query=test"
            )
            
            if search_response.status_code == 200:
                print("✅ Debug vector search endpoint working")
                return True
            else:
                print(f"❌ Debug vector search failed: {search_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error during debug endpoint testing: {str(e)}")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        print("🚀 Starting comprehensive admin endpoint tests...")
        print("=" * 60)
        
        results = {}
        
        # Authenticate admin
        if not self.authenticate_admin():
            print("❌ Cannot proceed without admin authentication")
            return {"authentication": False}
        
        # Test basic functionality
        results["health_check"] = self.test_health_check()
        results["debug_endpoints"] = self.test_debug_endpoints()
        
        # Test role management
        results["list_roles"] = self.test_list_roles()
        created_role = self.test_create_role()
        results["create_role"] = created_role is not None
        
        # Test document permissions
        document_id = self.get_test_document_id()
        if document_id and created_role:
            created_permission = self.test_create_document_permission(document_id, created_role["id"])
            results["create_document_permission"] = created_permission is not None
            
            results["list_document_permissions"] = self.test_list_document_permissions(document_id)
            
            if created_permission:
                results["revoke_document_permission"] = self.test_revoke_document_permission(
                    document_id, created_permission["id"]
                )
        else:
            results["create_document_permission"] = False
            results["list_document_permissions"] = False
            results["revoke_document_permission"] = False
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name}: {status}")
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! New admin endpoints are working correctly.")
        else:
            print("⚠️  Some tests failed. Please check the implementation.")
        
        return results


def main():
    """Main test function"""
    print("🧪 Admin Endpoints Test Suite")
    print("Testing new role creation and document permission management endpoints")
    print("=" * 60)
    
    # Initialize tester
    tester = AdminEndpointTester(BASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD)
    
    # Run all tests
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    all_passed = all(results.values())
    exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()