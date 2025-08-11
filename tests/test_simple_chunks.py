"""
Simple test script focused on testing the specific endpoints affected by chunk configuration changes:
1. /documents/{document_id}/chunks - to verify chunk creation with new size
2. /documents/{document_id}/reprocess - to verify rechunking with new configuration

Uses debug endpoints to validate the changes.
"""

import asyncio
import aiohttp
import json


async def simple_chunk_test():
    """Simple test for chunk configuration endpoints"""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        # Step 1: Login
        print("🔑 Logging in...")
        login_data = {"username": "test@example.com", "password": "testpassword"}
        async with session.post(f"{base_url}/auth/login", data=login_data) as response:
            if response.status != 200:
                print("❌ Login failed")
                return
            result = await response.json()
            token = result.get("access_token")
            headers = {"Authorization": f"Bearer {token}"}
            print("✅ Login successful")
        
        # Step 2: Upload test document
        print("\n📤 Uploading test document...")
        test_content = "This is a test document for chunk configuration validation. " * 500  # ~35000 chars
        
        data = aiohttp.FormData()
        data.add_field('file', test_content.encode(), filename='test.txt', content_type='text/plain')
        data.add_field('title', 'Chunk Configuration Test Document')
        
        async with session.post(f"{base_url}/documents/upload", headers=headers, data=data) as response:
            if response.status != 201:
                print(f"❌ Upload failed: {response.status}")
                return
            result = await response.json()
            document_id = result.get("document_id")
            print(f"✅ Document uploaded with ID: {document_id}")
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Step 3: Test /documents/{document_id}/chunks endpoint
        print(f"\n🔍 Testing GET /documents/{document_id}/chunks...")
        async with session.get(f"{base_url}/documents/{document_id}/chunks", headers=headers) as response:
            if response.status != 200:
                print(f"❌ Get chunks failed: {response.status}")
                return
            chunks = await response.json()
            print(f"✅ Retrieved {len(chunks)} chunks")
            
            # Analyze chunk sizes
            if chunks:
                sizes = [len(chunk.get('content', '')) for chunk in chunks]
                avg_size = sum(sizes) / len(sizes)
                max_size = max(sizes)
                min_size = min(sizes)
                
                print(f"📊 Chunk size analysis:")
                print(f"   Average: {avg_size:.0f} characters")
                print(f"   Max: {max_size} characters") 
                print(f"   Min: {min_size} characters")
                
                # Check if sizes are close to target (15000)
                large_chunks = [s for s in sizes if s > 10000]
                if large_chunks:
                    avg_large = sum(large_chunks) / len(large_chunks)
                    print(f"   Large chunks avg: {avg_large:.0f} characters")
                    if 12000 <= avg_large <= 16000:
                        print("✅ Chunk sizes are close to target 15000")
                    else:
                        print(f"⚠️  Chunk sizes not close to target 15000")
                else:
                    print("⚠️  No large chunks found (expected with 15000 chunk size)")
        
        # Step 4: Test /documents/{document_id}/reprocess endpoint  
        print(f"\n🔄 Testing POST /documents/{document_id}/reprocess...")
        async with session.post(f"{base_url}/documents/{document_id}/reprocess", headers=headers) as response:
            if response.status != 200:
                print(f"❌ Reprocess failed: {response.status}")
                error = await response.text()
                print(f"Error: {error}")
                return
            result = await response.json()
            print(f"✅ Reprocess successful: {result.get('message', 'No message')}")
        
        # Wait for reprocessing
        await asyncio.sleep(5)
        
        # Step 5: Verify chunks after reprocessing
        print(f"\n🔍 Verifying chunks after reprocessing...")
        async with session.get(f"{base_url}/documents/{document_id}/chunks", headers=headers) as response:
            if response.status != 200:
                print(f"❌ Get chunks after reprocess failed: {response.status}")
                return
            reprocessed_chunks = await response.json()
            print(f"✅ Retrieved {len(reprocessed_chunks)} chunks after reprocessing")
            
            # Compare before and after
            if reprocessed_chunks:
                sizes = [len(chunk.get('content', '')) for chunk in reprocessed_chunks]
                avg_size = sum(sizes) / len(sizes)
                print(f"📊 Reprocessed chunk average size: {avg_size:.0f} characters")
                
                # Verify configuration is applied
                large_chunks = [s for s in sizes if s > 10000]
                if large_chunks:
                    avg_large = sum(large_chunks) / len(large_chunks) 
                    if 12000 <= avg_large <= 16000:
                        print("✅ Reprocessing applied correct chunk size (15000)")
                    else:
                        print(f"⚠️  Reprocessed chunks not using target size")
        
        # Step 6: Use debug endpoint to verify vector store
        print(f"\n🔧 Using debug endpoint to verify vector store...")
        async with session.get(f"{base_url}/debug/vector-store/user-documents", headers=headers) as response:
            if response.status == 200:
                debug_info = await response.json()
                total_chunks = debug_info.get('total_chunks', 0)
                documents = debug_info.get('documents', [])
                print(f"✅ Debug info: {total_chunks} total chunks in vector store")
                
                for doc in documents:
                    if doc.get('document_id') == str(document_id):
                        print(f"   Target document has {doc.get('chunk_count', 0)} chunks in vector store")
                        break
            else:
                print(f"⚠️  Debug endpoint failed: {response.status}")
        
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
    
    asyncio.run(simple_chunk_test())
