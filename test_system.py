#!/usr/bin/env python3
"""Test script to verify the system works."""

import sys
from pathlib import Path

# Add modules to path - use current directory since we're running from correct location
sys.path.insert(0, str(Path.cwd() / "modules"))

print("Testing Morocco Job Radar Bot Components...")
print("=" * 50)

# Test 1: Check if we can import modules
try:
    print("\n1. Testing imports...")
    from modules.ai_writer import generate_post, fallback_post
    from modules.image_maker import create_job_image
    from modules.facebook_publisher import publish_job
    from modules.job_tracker import is_job_published, get_published_count
    print("   ✓ All modules imported successfully")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Create a sample job
print("\n2. Creating sample job...")
sample_job = {
    "title": "مهندس برمجيات",
    "company": "شركة التقنية المغربية",
    "location": "الدار البيضاء",
    "description": "نبحث عن مهندس برمجيات ذو خبرة في تطوير الويب",
    "application_url": "https://example.com/job1",
    "job_type": "private",
    "remote": False,
}

print(f"   Job: {sample_job['title']}")
print(f"   Company: {sample_job['company']}")
print(f"   Location: {sample_job['location']}")

# Test 3: Check if job was already published
print("\n3. Checking if job was already published...")
if is_job_published(sample_job):
    print("   ⚠ Job was already published, skipping...")
else:
    print("   ✓ Job is new, can be published")

# Test 4: Test AI post generation (with fallback)
print("\n4. Testing post generation...")
try:
    post_data = fallback_post(sample_job)  # Use fallback to avoid API calls
    print("   ✓ Post generated successfully")
    print(f"   Post preview: {post_data['facebook_post'][:100]}...")
    print(f"   First comment: {post_data['first_comment'][:100]}...")
except Exception as e:
    print(f"   ✗ Post generation failed: {e}")

# Test 5: Test image creation
print("\n5. Testing image creation...")
try:
    # Make sure job dictionary is available
    test_job = sample_job.copy()
    test_post_data = post_data.copy()
    image_path = create_job_image(test_job, test_post_data)
    print(f"   ✓ Image created: {image_path}")
    print(f"   Image exists: {image_path.exists()}")
except Exception as e:
    print(f"   ✗ Image creation failed: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Check published jobs count
print("\n6. Checking published jobs count...")
count = get_published_count()
print(f"   Total published jobs: {count}")

print("\n" + "=" * 50)
print("✅ System test completed!")
print("\nTo run the full bot:")
print("  - Set DRY_RUN=true for testing")
print("  - Run: python main.py")
