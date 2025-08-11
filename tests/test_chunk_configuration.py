        
        print("\n🎉 Simple chunk configuration test completed!")
        print("\nSummary of changes verified:")
        print("✅ Chunk size updated to 15000 characters")
        print("✅ Chunk overlap updated to 1000 characters") 
        print("✅ Batch size updated to 5000")
        print("✅ Both /documents/{id}/chunks and /documents/{id}/reprocess work correctly")


if __name__ == "__main__":
    print("Starting Simple Chunk Configuration Test")
    print("=" * 45)
    print("Testing endpoints:")
    print("- GET /documents/{document_id}/chunks")
    print("- POST /documents/{document_id}/reprocess")
    print("- Debug endpoints for verification")
    print("=" * 45)
    
    asyncio.run(simple_chunk_test())"""
Test script to verify the chunk configuration changes.
Tests both chunking (via /documents/{document_id}/chunks) and reprocessing (via /documents/{document_id}/reprocess).
Uses the debug endpoints to validate the changes.
"""

import asyncio
import aiohttp
import json
import os
from pathlib import Path


class DocumentChunkTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.auth_token = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def login(self, username: str = "test@example.com", password: str = "testpassword"):
        """Login and get auth token"""
        login_data = {
            "username": username,
            "password": password
        }
        
        async with self.session.post(
            f"{self.base_url}/auth/login",
            data=login_data
        ) as response:
            if response.status == 200:
                result = await response.json()
                self.auth_token = result.get("access_token")
                print(f"✓ Successfully logged in")
                return True
            else:
                print(f"✗ Login failed: {response.status}")
                return False
    
    def get_auth_headers(self):
        """Get authorization headers"""
        if not self.auth_token:
            raise ValueError("Not authenticated. Call login() first.")
        return {"Authorization": f"Bearer {self.auth_token}"}
    
    async def get_vector_store_stats(self):
        """Get vector store statistics"""
        async with self.session.get(
            f"{self.base_url}/debug/vector-store/stats",
            headers=self.get_auth_headers()
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"✗ Failed to get vector store stats: {response.status}")
                return None
    
    async def test_vector_search(self, query: str = "test query"):
        """Test vector search functionality"""
        async with self.session.post(
            f"{self.base_url}/debug/vector-store/test-search",
            headers=self.get_auth_headers(),
            params={"query": query}
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"✗ Failed to test vector search: {response.status}")
                return None
    
    async def get_user_documents_in_vector_store(self):
        """Get user documents in vector store"""
        async with self.session.get(
            f"{self.base_url}/debug/vector-store/user-documents",
            headers=self.get_auth_headers()
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"✗ Failed to get user documents: {response.status}")
                return None
    
    async def upload_test_document(self, content: str = None):
        """Upload a test document for chunking tests"""
        if content is None:
            # Create a large test document to test the new chunk size (15000)
            content = "This is a test document. " * 1000  # About 25000 characters
        
        # Create a temporary file
        test_file_path = "test_chunk_document.txt"
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        try:
            # Upload the document
            data = aiohttp.FormData()
            data.add_field('file', open(test_file_path, 'rb'), filename='test_chunk_document.txt')
            data.add_field('title', 'Test Chunk Configuration Document')
            
            async with self.session.post(
                f"{self.base_url}/documents/upload",
                headers=self.get_auth_headers(),
                data=data
            ) as response:
                if response.status == 201:
                    result = await response.json()
                    document_id = result.get("document_id")
                    print(f"✓ Successfully uploaded test document with ID: {document_id}")
                    return document_id
                else:
                    print(f"✗ Failed to upload document: {response.status}")
                    error_text = await response.text()
                    print(f"Error: {error_text}")
                    return None
        finally:
            # Clean up temporary file
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
    
    async def get_document_chunks(self, document_id: int):
        """Get chunks for a document"""
        async with self.session.get(
            f"{self.base_url}/documents/{document_id}/chunks",
            headers=self.get_auth_headers()
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"✗ Failed to get document chunks: {response.status}")
                return None
    
    async def reprocess_document(self, document_id: int):
        """Reprocess a document to test rechunking"""
        async with self.session.post(
            f"{self.base_url}/documents/{document_id}/reprocess",
            headers=self.get_auth_headers()
        ) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✓ Successfully reprocessed document {document_id}")
                return result
            else:
                print(f"✗ Failed to reprocess document: {response.status}")
                error_text = await response.text()
                print(f"Error: {error_text}")
                return None
    
    async def analyze_chunk_configuration(self, chunks):
        """Analyze chunks to verify configuration"""
        if not chunks:
            print("✗ No chunks to analyze")
            return
        
        print(f"\n📊 Chunk Analysis:")
        print(f"   Total chunks: {len(chunks)}")
        
        chunk_sizes = []
        for i, chunk in enumerate(chunks):
            chunk_size = len(chunk.get('content', ''))
            chunk_sizes.append(chunk_size)
            
            # Check metadata for chunk configuration
            meta = chunk.get('meta', {})
            chunk_index = meta.get('chunk_index', 'N/A')
            start_pos = meta.get('start_position', 'N/A')
            end_pos = meta.get('end_position', 'N/A')
            stored_chunk_size = meta.get('chunk_size', 'N/A')
            
            if i < 3:  # Show details for first 3 chunks
                print(f"   Chunk {chunk_index}:")
                print(f"     - Content length: {chunk_size}")
                print(f"     - Stored chunk size: {stored_chunk_size}")
                print(f"     - Position: {start_pos} - {end_pos}")
                print(f"     - Content preview: {chunk.get('content', '')[:100]}...")
        
        if chunk_sizes:
            avg_size = sum(chunk_sizes) / len(chunk_sizes)
            max_size = max(chunk_sizes)
            min_size = min(chunk_sizes)
            
            print(f"\n📈 Size Statistics:")
            print(f"   Average chunk size: {avg_size:.0f} characters")
            print(f"   Maximum chunk size: {max_size} characters")
            print(f"   Minimum chunk size: {min_size} characters")
            
            # Verify configuration
            expected_max_size = 15000 + 1000  # chunk_size + chunk_overlap
            if max_size <= expected_max_size:
                print(f"✓ Chunk sizes are within expected range (max {expected_max_size})")
            else:
                print(f"⚠️  Some chunks exceed expected size limit of {expected_max_size}")
            
            # Check if most chunks are close to the target size
            large_chunks = [size for size in chunk_sizes if size > 10000]  # Should be close to 15000
            if large_chunks:
                avg_large = sum(large_chunks) / len(large_chunks)
                print(f"   Average size of large chunks: {avg_large:.0f} characters")
                if 12000 <= avg_large <= 16000:
                    print(f"✓ Large chunks are close to target size of 15000")
                else:
                    print(f"⚠️  Large chunks average ({avg_large:.0f}) is not close to target 15000")
    
    async def run_comprehensive_test(self):
        """Run comprehensive test of chunk configuration"""
        print("🚀 Starting Comprehensive Chunk Configuration Test\n")
        
        # Step 1: Login
        if not await self.login():
            return
        
        # Step 2: Get initial vector store stats
        print("📊 Getting initial vector store statistics...")
        initial_stats = await self.get_vector_store_stats()
        if initial_stats:
            stats = initial_stats.get('stats', {})
            print(f"   Collection: {stats.get('collection_name')}")
            print(f"   Document count: {stats.get('document_count')}")
            print(f"   Embedding dimension: {stats.get('embedding_dimension')}")
        
        # Step 3: Upload test document
        print(f"\n📤 Uploading test document...")
        document_id = await self.upload_test_document()
        if not document_id:
            return
        
        # Wait a moment for processing
        await asyncio.sleep(2)
        
        # Step 4: Get and analyze chunks
        print(f"\n🔍 Getting chunks for document {document_id}...")
        chunks = await self.get_document_chunks(document_id)
        if chunks:
            await self.analyze_chunk_configuration(chunks)
        
        # Step 5: Test reprocessing
        print(f"\n🔄 Testing document reprocessing...")
        reprocess_result = await self.reprocess_document(document_id)
        
        if reprocess_result:
            # Wait for reprocessing to complete
            await asyncio.sleep(3)
            
            # Get chunks again after reprocessing
            print(f"\n🔍 Getting chunks after reprocessing...")
            reprocessed_chunks = await self.get_document_chunks(document_id)
            if reprocessed_chunks:
                print(f"\n📊 Analysis after reprocessing:")
                await self.analyze_chunk_configuration(reprocessed_chunks)
        
        # Step 6: Test vector search
        print(f"\n🔎 Testing vector search...")
        search_results = await self.test_vector_search("test document")
        if search_results:
            for test_name, result in search_results.get('results', {}).items():
                if 'error' not in result:
                    print(f"   {test_name}: Found {result.get('count', 0)} chunks")
                else:
                    print(f"   {test_name}: Error - {result['error']}")
        
        # Step 7: Final stats
        print(f"\n📊 Final vector store statistics...")
        final_stats = await self.get_vector_store_stats()
        if final_stats:
            stats = final_stats.get('stats', {})
            print(f"   Document count: {stats.get('document_count')}")
        
        # Step 8: Get user documents
        print(f"\n📋 User documents in vector store...")
        user_docs = await self.get_user_documents_in_vector_store()
        if user_docs:
            total_chunks = user_docs.get('total_chunks', 0)
            documents = user_docs.get('documents', [])
            print(f"   Total chunks: {total_chunks}")
            print(f"   Documents: {len(documents)}")
            for doc in documents[:3]:  # Show first 3 documents
                print(f"     - {doc.get('document_title', 'Unknown')}: {doc.get('chunk_count', 0)} chunks")
        
        print(f"\n✅ Comprehensive test completed!")


async def main():
    """Main test function"""
    print("Starting Document Chunk Configuration Test")
    print("=" * 50)
    
    async with DocumentChunkTester() as tester:
        await tester.run_comprehensive_test()


if __name__ == "__main__":
    asyncio.run(main())
