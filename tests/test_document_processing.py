#!/usr/bin/env python3
"""
Test script to verify document processing and embedding storage.
Run this after starting the application to test the fixes.
"""

import asyncio
import aiohttp
import json
import sys
from pathlib import Path


class DocumentProcessingTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        self.document_id = None
        
    async def test_login(self, username="testuser", password="testpass123"):
        """Test user login"""
        print("\n1. Testing login...")
        async with aiohttp.ClientSession() as session:
            # First try to register (in case user doesn't exist)
            try:
                async with session.post(
                    f"{self.base_url}/auth/register",
                    json={
                        "email": f"{username}@example.com",
                        "username": username,
                        "password": password,
                        "full_name": "Test User"
                    }
                ) as response:
                    if response.status == 201:
                        print("   ✓ User registered successfully")
            except:
                pass
            
            # Now login
            data = aiohttp.FormData()
            data.add_field('username', username)
            data.add_field('password', password)
            
            async with session.post(
                f"{self.base_url}/auth/login",
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.token = result["access_token"]
                    print(f"   ✓ Login successful, token obtained")
                    return True
                else:
                    print(f"   ✗ Login failed: {response.status}")
                    return False
    
    async def test_upload_document(self, file_path=None):
        """Test document upload with a sample text file"""
        print("\n2. Testing document upload...")
        
        if not file_path:
            # Create a sample document
            sample_content = """
            # Sample Document for Testing
            
            This is a test document to verify that document processing, chunking, 
            and embedding generation are working correctly.
            
            ## Section 1: Introduction
            The document processing system should be able to:
            1. Extract text from various file formats
            2. Split the text into manageable chunks
            3. Generate embeddings for each chunk
            4. Store the chunks and embeddings in the vector store
            
            ## Section 2: Technical Details
            The chunking process uses a sliding window approach with configurable 
            chunk size and overlap. This ensures that context is preserved across 
            chunk boundaries, which is important for retrieval accuracy.
            
            ## Section 3: Verification
            After processing, we should be able to:
            - Query the document chunks endpoint to see all chunks
            - Search for content using semantic similarity
            - Retrieve relevant chunks when asking questions
            
            This concludes our test document. It should be split into multiple 
            chunks based on the configured chunk size.
            """ * 5  # Repeat to ensure multiple chunks
            
            # Save to temp file
            temp_file = Path("test_document.txt")
            temp_file.write_text(sample_content)
            file_path = str(temp_file)
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            data = aiohttp.FormData()
            data.add_field('file',
                          open(file_path, 'rb'),
                          filename='test_document.txt',
                          content_type='text/plain')
            data.add_field('title', 'Test Document for Chunking')
            
            async with session.post(
                f"{self.base_url}/documents/upload",
                headers=headers,
                data=data
            ) as response:
                if response.status == 201:
                    result = await response.json()
                    self.document_id = result["document_id"]
                    print(f"   ✓ Document uploaded successfully")
                    print(f"     Document ID: {self.document_id}")
                    print(f"     File size: {result['file_size']} bytes")
                    return True
                else:
                    error = await response.text()
                    print(f"   ✗ Upload failed: {response.status}")
                    print(f"     Error: {error}")
                    return False
    
    async def test_get_document(self):
        """Test retrieving document details"""
        print("\n3. Testing document retrieval...")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with session.get(
                f"{self.base_url}/documents/{self.document_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✓ Document retrieved successfully")
                    print(f"     Title: {result['title']}")
                    print(f"     Status: {result['status']}")
                    print(f"     Chunk count: {result['chunk_count']}")
                    
                    if result['status'] == 'failed':
                        print(f"     ⚠ Processing failed: {result.get('meta', {}).get('error', 'Unknown error')}")
                        return False
                    return True
                else:
                    print(f"   ✗ Retrieval failed: {response.status}")
                    return False
    
    async def test_get_chunks(self):
        """Test retrieving document chunks"""
        print("\n4. Testing chunk retrieval...")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with session.get(
                f"{self.base_url}/documents/{self.document_id}/chunks",
                headers=headers
            ) as response:
                if response.status == 200:
                    chunks = await response.json()
                    print(f"   ✓ Chunks retrieved successfully")
                    print(f"     Number of chunks: {len(chunks)}")
                    
                    if chunks:
                        print(f"     First chunk preview: {chunks[0]['content'][:100]}...")
                        print(f"     Chunk metadata: {chunks[0].get('meta', {})}")
                    else:
                        print("     ⚠ No chunks found!")
                        return False
                    return True
                else:
                    print(f"   ✗ Chunk retrieval failed: {response.status}")
                    return False
    
    async def test_search(self):
        """Test searching for content in documents"""
        print("\n5. Testing semantic search...")
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            search_query = "chunking process and embeddings"
            
            async with session.post(
                f"{self.base_url}/chat/search",
                headers=headers,
                json={
                    "query": search_query,
                    "max_results": 3,
                    "similarity_threshold": 0.5
                }
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    print(f"   ✓ Search completed successfully")
                    print(f"     Query: '{search_query}'")
                    print(f"     Results found: {len(results)}")
                    
                    for i, result in enumerate(results, 1):
                        print(f"     Result {i}:")
                        print(f"       Score: {result.get('score', 'N/A')}")
                        print(f"       Content preview: {result['content'][:100]}...")
                    
                    if not results:
                        print("     ⚠ No results found - embeddings might not be stored correctly")
                        return False
                    return True
                else:
                    print(f"   ✗ Search failed: {response.status}")
                    return False
    
    async def test_chat(self):
        """Test chatting with document context"""
        print("\n6. Testing chat with document context...")
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            question = "What are the main capabilities of the document processing system according to the uploaded document?"
            
            async with session.post(
                f"{self.base_url}/chat/",
                headers=headers,
                json={
                    "message": question,
                    "use_vector_search": True,
                    "max_chunks": 5
                }
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✓ Chat response received")
                    print(f"     Question: {question}")
                    print(f"     Answer: {result['message'][:200]}...")
                    print(f"     Sources used: {len(result.get('sources', []))}")
                    
                    if result.get('sources'):
                        print("     Source chunks found and used ✓")
                    else:
                        print("     ⚠ No source chunks used - vector search might not be working")
                    return True
                else:
                    print(f"   ✗ Chat failed: {response.status}")
                    return False
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*60)
        print("DOCUMENT PROCESSING TEST SUITE")
        print("="*60)
        
        all_passed = True
        
        # Run tests
        if not await self.test_login():
            print("\n❌ Login failed - cannot continue")
            return False
        
        if not await self.test_upload_document():
            print("\n❌ Document upload failed - cannot continue")
            return False
        
        # Wait a bit for processing to complete
        print("\n⏳ Waiting for document processing to complete...")
        await asyncio.sleep(5)
        
        if not await self.test_get_document():
            all_passed = False
        
        if not await self.test_get_chunks():
            all_passed = False
        
        # Wait a bit more for vector store indexing
        await asyncio.sleep(2)
        
        if not await self.test_search():
            all_passed = False
        
        if not await self.test_chat():
            all_passed = False
        
        # Summary
        print("\n" + "="*60)
        if all_passed:
            print("✅ ALL TESTS PASSED!")
            print("Document processing, chunking, and embedding storage are working correctly.")
        else:
            print("⚠️ SOME TESTS FAILED")
            print("Please check the logs for more details.")
        print("="*60)
        
        # Cleanup
        try:
            Path("test_document.txt").unlink()
        except:
            pass
        
        return all_passed


async def main():
    """Main test runner"""
    tester = DocumentProcessingTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
