"""
Test file for the /chat/search endpoint with document upload
This test demonstrates how to:
1. Upload a document
2. Wait for processing
3. Use the search endpoint to find relevant content

Run this after the conversation endpoint tests to verify search functionality.
"""

import asyncio
import aiohttp
import json
import tempfile
import os
from typing import Optional, Dict, Any
from datetime import datetime


class SearchEndpointTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_token: Optional[str] = None
        self.test_user = {
            "email": f"search_test_{datetime.now().timestamp()}@example.com",
            "username": f"searchuser_{int(datetime.now().timestamp())}",
            "password": "TestPassword123!",
            "full_name": "Search Test User"
        }
        self.document_id: Optional[int] = None
        
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
    
    async def register_and_login(self) -> bool:
        """Register a new user and login to get auth token"""
        try:
            # Register user
            # async with self.session.post(
            #     f"{self.base_url}/auth/register",
            #     json=self.test_user
            # ) as resp:
            #     if resp.status != 200:
            #         error_text = await resp.text()
            #         self.print_result("User Registration", False, f"Failed to register user: {resp.status}", error_text)
            #         return False
                    
            # Login
            form_data = aiohttp.FormData()
            form_data.add_field('username', 'string')
            form_data.add_field('password', 'stringing')
            
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
            "Authorization": f"Bearer {self.auth_token}"
        }
    
    def create_test_document(self) -> str:
        """Create a test document file"""
        content = """
        # Test Document for Search Functionality
        
        ## Introduction
        This is a test document created to verify the search functionality of the RAG system.
        It contains various topics that can be searched.
        
        ## Machine Learning Section
        Machine learning is a subset of artificial intelligence that focuses on the development 
        of algorithms and statistical models that enable computer systems to improve their 
        performance on a specific task through experience.
        
        ### Deep Learning
        Deep learning is a subset of machine learning that uses neural networks with multiple 
        layers (deep neural networks) to progressively extract higher-level features from raw input.
        
        ## Natural Language Processing
        Natural Language Processing (NLP) is a branch of artificial intelligence that helps 
        computers understand, interpret and manipulate human language. NLP draws from many 
        disciplines including computer science and computational linguistics.
        
        ### Applications of NLP
        - Text Classification
        - Named Entity Recognition
        - Machine Translation
        - Question Answering Systems
        - Sentiment Analysis
        
        ## Climate Change and Technology
        Technology plays a crucial role in addressing climate change. From renewable energy 
        solutions to carbon capture technologies, innovation is key to mitigating environmental impact.
        
        ## Quantum Computing
        Quantum computing represents a fundamental shift in computation, using quantum mechanical 
        phenomena such as superposition and entanglement to perform operations on data.
        
        ## Conclusion
        This document serves as a test corpus for the document search and retrieval system.
        Each section contains distinct topics that should be searchable through the vector store.
        """
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            return f.name
    
    async def upload_document(self) -> bool:
        """Upload a test document"""
        test_file_path = None
        try:
            # Create test document
            test_file_path = self.create_test_document()
            
            # Prepare multipart form data
            with open(test_file_path, 'rb') as f:
                form_data = aiohttp.FormData()
                form_data.add_field('file',
                                   f,
                                   filename='test_document.txt',
                                   content_type='text/plain')
                form_data.add_field('title', 'Test Document for Search')
                
                async with self.session.post(
                    f"{self.base_url}/documents/upload",
                    headers=self.get_headers(),
                    data=form_data
                ) as resp:
                    if resp.status == 201:
                        data = await resp.json()
                        self.document_id = data.get('document_id')
                        self.print_result(
                            "Document Upload",
                            True,
                            "Successfully uploaded test document",
                            {
                                "document_id": self.document_id,
                                "filename": data.get('filename'),
                                "file_size": data.get('file_size')
                            }
                        )
                        return True
                    else:
                        error_text = await resp.text()
                        self.print_result(
                            "Document Upload",
                            False,
                            f"Failed with status {resp.status}",
                            error_text
                        )
                        return False
                        
        except Exception as e:
            self.print_result("Document Upload", False, f"Error: {str(e)}")
            return False
        finally:
            # Clean up temporary file
            if test_file_path and os.path.exists(test_file_path):
                os.unlink(test_file_path)
    
    async def wait_for_processing(self) -> bool:
        """Wait for document to be processed"""
        if not self.document_id:
            return False
            
        max_attempts = 30  # Wait up to 30 seconds
        attempt = 0
        
        print("\n⏳ Waiting for document processing...")
        
        while attempt < max_attempts:
            try:
                async with self.session.get(
                    f"{self.base_url}/documents/{self.document_id}",
                    headers=self.get_headers()
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        status = data.get('status')
                        
                        if status == 'completed':
                            self.print_result(
                                "Document Processing",
                                True,
                                "Document processed successfully",
                                {
                                    "status": status,
                                    "chunk_count": data.get('chunk_count')
                                }
                            )
                            return True
                        elif status == 'failed':
                            self.print_result(
                                "Document Processing",
                                False,
                                "Document processing failed",
                                {"status": status}
                            )
                            return False
                        else:
                            print(f"  Status: {status} (attempt {attempt + 1}/{max_attempts})")
                            
            except Exception as e:
                print(f"  Error checking status: {str(e)}")
            
            await asyncio.sleep(1)
            attempt += 1
        
        self.print_result(
            "Document Processing",
            False,
            "Timeout waiting for document processing",
            None
        )
        return False
    
    async def test_search_queries(self):
        """Test various search queries"""
        test_queries = [
            {
                "query": "machine learning",
                "expected_topics": ["machine learning", "artificial intelligence", "algorithms"],
                "max_results": 5,
                "similarity_threshold": 0.5
            },
            {
                "query": "climate change technology",
                "expected_topics": ["climate change", "renewable energy", "environmental"],
                "max_results": 3,
                "similarity_threshold": 0.6
            },
            {
                "query": "quantum computing",
                "expected_topics": ["quantum", "computation", "superposition"],
                "max_results": 5,
                "similarity_threshold": 0.5
            },
            {
                "query": "NLP applications",
                "expected_topics": ["natural language", "text classification", "sentiment"],
                "max_results": 5,
                "similarity_threshold": 0.5
            },
            {
                "query": "deep neural networks",
                "expected_topics": ["deep learning", "neural networks", "layers"],
                "max_results": 5,
                "similarity_threshold": 0.5
            }
        ]
        
        for test_case in test_queries:
            await self.perform_search(test_case)
    
    async def perform_search(self, test_case: Dict[str, Any]):
        """Perform a single search test"""
        try:
            # Search using POST request with JSON body
            search_body = {
                "query": test_case["query"],
                "max_results": test_case["max_results"],
                "similarity_threshold": test_case["similarity_threshold"]
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/search",
                headers=self.get_headers(),
                json=search_body
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Check if any expected topics are found in results
                    found_relevant = False
                    relevant_chunks = []
                    
                    for chunk in data:
                        chunk_content = chunk.get('content', '').lower()
                        for expected in test_case['expected_topics']:
                            if expected.lower() in chunk_content:
                                found_relevant = True
                                relevant_chunks.append({
                                    'preview': chunk_content[:100] + '...',
                                    'score': chunk.get('score')
                                })
                                break
                    
                    self.print_result(
                        f"Search: '{test_case['query']}'",
                        True,
                        f"Found {len(data)} results",
                        {
                            "total_results": len(data),
                            "found_relevant_content": found_relevant,
                            "relevant_chunks_count": len(relevant_chunks),
                            "top_scores": [chunk.get('score') for chunk in data[:3]]
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        f"Search: '{test_case['query']}'",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result(
                f"Search: '{test_case['query']}'",
                False,
                f"Error: {str(e)}"
            )
    
    async def test_search_with_filters(self):
        """Test search with document ID filters"""
        if not self.document_id:
            self.print_result("Search with Filters", False, "No document ID available")
            return
            
        try:
            search_body = {
                "query": "machine learning",
                "max_results": 5,
                "similarity_threshold": 0.5,
                "document_ids": [str(self.document_id)]
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/search",
                headers=self.get_headers(),
                json=search_body
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Search with Document Filter",
                        True,
                        f"Successfully filtered search to document {self.document_id}",
                        {
                            "results_count": len(data),
                            "document_ids_filter": [str(self.document_id)]
                        }
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Search with Document Filter",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("Search with Document Filter", False, f"Error: {str(e)}")
    
    async def test_empty_search(self):
        """Test search with no matching content"""
        try:
            search_body = {
                "query": "xyzabc123nonexistent",
                "max_results": 5,
                "similarity_threshold": 0.9  # High threshold
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/search",
                headers=self.get_headers(),
                json=search_body
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.print_result(
                        "Empty Search Result",
                        True,
                        f"Search completed with {len(data)} results (expected low/zero for non-existent term)",
                        {"results_count": len(data)}
                    )
                else:
                    error_text = await resp.text()
                    self.print_result(
                        "Empty Search Result",
                        False,
                        f"Failed with status {resp.status}",
                        error_text
                    )
                    
        except Exception as e:
            self.print_result("Empty Search Result", False, f"Error: {str(e)}")
    
    async def run_all_tests(self):
        """Run all search endpoint tests"""
        print("=" * 60)
        print("SEARCH ENDPOINT TEST SUITE")
        print("=" * 60)
        print(f"Testing against: {self.base_url}")
        print(f"Started at: {datetime.now().isoformat()}")
        print("-" * 60)
        
        # Authenticate first
        if not await self.register_and_login():
            print("\n❌ CRITICAL: Authentication failed. Cannot proceed with tests.")
            return
        
        # Upload and process a document
        print("\n" + "=" * 60)
        print("DOCUMENT PREPARATION")
        print("=" * 60)
        
        if not await self.upload_document():
            print("\n❌ CRITICAL: Document upload failed. Cannot test search.")
            return
        
        if not await self.wait_for_processing():
            print("\n❌ CRITICAL: Document processing failed. Cannot test search.")
            return
        
        # Run search tests
        print("\n" + "=" * 60)
        print("RUNNING SEARCH TESTS")
        print("=" * 60)
        
        await self.test_search_queries()
        await self.test_search_with_filters()
        await self.test_empty_search()
        
        print("\n" + "=" * 60)
        print("TEST SUITE COMPLETED")
        print(f"Finished at: {datetime.now().isoformat()}")
        print("=" * 60)


async def main():
    """Main function to run tests"""
    async with SearchEndpointTester() as tester:
        await tester.run_all_tests()


if __name__ == "__main__":
    print("\n🔍 SEARCH ENDPOINT TESTER")
    print("This script tests the /chat/search endpoint with document upload and processing.")
    print("\nMake sure the server is running on http://localhost:8000")
    print("Press Ctrl+C to cancel...\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
