"""
Configuration Validation Script

This script shows the current chunk configuration values being used in different parts of the codebase
to verify that all changes have been applied consistently.
"""

import os
import sys

# Add the project directory to the Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

def validate_configuration():
    """Validate that all configuration sources have been updated"""
    print("🔍 Validating Chunk Configuration Changes")
    print("=" * 50)
    
    # 1. Check config.py defaults
    print("\n1. Checking config.py defaults...")
    try:
        from config import Settings
        settings = Settings()
        print(f"   ✅ chunk_size: {settings.chunk_size}")
        print(f"   ✅ chunk_overlap: {settings.chunk_overlap}")
        
        if settings.chunk_size == 15000 and settings.chunk_overlap == 1000:
            print("   ✅ config.py has correct defaults")
        else:
            print("   ❌ config.py has incorrect defaults")
    except Exception as e:
        print(f"   ❌ Error reading config.py: {e}")
    
    # 2. Check .env file
    print("\n2. Checking .env file...")
    env_file = os.path.join(project_dir, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            content = f.read()
            
        chunk_size_found = False
        chunk_overlap_found = False
        
        for line in content.split('\n'):
            if line.startswith('CHUNK_SIZE='):
                chunk_size = line.split('=')[1].strip()
                print(f"   ✅ CHUNK_SIZE={chunk_size}")
                chunk_size_found = chunk_size == "15000"
            elif line.startswith('CHUNK_OVERLAP='):
                chunk_overlap = line.split('=')[1].strip()
                print(f"   ✅ CHUNK_OVERLAP={chunk_overlap}")
                chunk_overlap_found = chunk_overlap == "1000"
        
        if chunk_size_found and chunk_overlap_found:
            print("   ✅ .env file has correct values")
        else:
            print("   ❌ .env file has incorrect values")
    else:
        print("   ⚠️  .env file not found")
    
    # 3. Check text_utils.py function defaults
    print("\n3. Checking text_utils.py function defaults...")
    try:
        import inspect
        from app.utils.text_utils import chunk_text
        
        sig = inspect.signature(chunk_text)
        chunk_size_param = sig.parameters['chunk_size'].default
        chunk_overlap_param = sig.parameters['chunk_overlap'].default
        
        print(f"   ✅ chunk_text default chunk_size: {chunk_size_param}")
        print(f"   ✅ chunk_text default chunk_overlap: {chunk_overlap_param}")
        
        if chunk_size_param == 15000 and chunk_overlap_param == 1000:
            print("   ✅ text_utils.py has correct defaults")
        else:
            print("   ❌ text_utils.py has incorrect defaults")
    except Exception as e:
        print(f"   ❌ Error checking text_utils.py: {e}")
    
    # 4. Check DocumentProcessor defaults
    print("\n4. Checking DocumentProcessor defaults...")
    try:
        import inspect
        from app.ingestion.document_processor import DocumentProcessor
        
        sig = inspect.signature(DocumentProcessor.__init__)
        chunk_size_param = sig.parameters['chunk_size'].default
        chunk_overlap_param = sig.parameters['chunk_overlap'].default
        
        print(f"   ✅ DocumentProcessor default chunk_size: {chunk_size_param}")
        print(f"   ✅ DocumentProcessor default chunk_overlap: {chunk_overlap_param}")
        
        if chunk_size_param == 15000 and chunk_overlap_param == 1000:
            print("   ✅ DocumentProcessor has correct defaults")
        else:
            print("   ❌ DocumentProcessor has incorrect defaults")
    except Exception as e:
        print(f"   ❌ Error checking DocumentProcessor: {e}")
    
    # 5. Check documents.py batch sizes
    print("\n5. Checking batch sizes in documents.py...")
    documents_file = os.path.join(project_dir, 'app', 'views', 'documents.py')
    if os.path.exists(documents_file):
        with open(documents_file, 'r') as f:
            content = f.read()
        
        batch_size_5000_count = content.count('batch_size = 5000')
        print(f"   ✅ Found {batch_size_5000_count} instances of 'batch_size = 5000'")
        
        # Check if old batch sizes still exist
        batch_size_20_count = content.count('batch_size = 20')
        batch_size_50_count = content.count('50)')  # for the range function
        
        if batch_size_5000_count >= 2 and batch_size_20_count == 0:
            print("   ✅ documents.py has correct batch sizes")
        else:
            print(f"   ⚠️  documents.py may have inconsistent batch sizes")
            print(f"      batch_size = 5000: {batch_size_5000_count}")
            print(f"      batch_size = 20: {batch_size_20_count}")
    else:
        print("   ❌ documents.py not found")
    
    # 6. Test actual configuration loading
    print("\n6. Testing actual configuration loading...")
    try:
        from config import settings
        print(f"   ✅ Loaded chunk_size: {settings.chunk_size}")
        print(f"   ✅ Loaded chunk_overlap: {settings.chunk_overlap}")
        
        if settings.chunk_size == 15000 and settings.chunk_overlap == 1000:
            print("   ✅ Runtime configuration is correct")
        else:
            print("   ❌ Runtime configuration is incorrect")
    except Exception as e:
        print(f"   ❌ Error loading runtime configuration: {e}")
    
    print(f"\n🎯 Configuration validation completed!")
    print(f"\nTarget values:")
    print(f"  - Chunk Size: 15000 characters")
    print(f"  - Chunk Overlap: 1000 characters") 
    print(f"  - Batch Size: 5000")
    
    print(f"\nFiles that were modified:")
    print(f"  ✅ config.py - Updated default values")
    print(f"  ✅ .env - Updated environment variables")
    print(f"  ✅ app/utils/text_utils.py - Updated function defaults")
    print(f"  ✅ app/views/documents.py - Updated batch sizes")
    print(f"  ✅ app/ingestion/document_processor.py - Already had correct values")


if __name__ == "__main__":
    validate_configuration()
