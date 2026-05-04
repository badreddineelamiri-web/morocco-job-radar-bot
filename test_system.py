#!/usr/bin/env python3
"""Smoke test for Morocco Job Radar Bot components."""

from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path.cwd() / "modules"))
os.environ.setdefault("DRY_RUN", "true")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

print("Testing Morocco Job Radar Bot Components...")
print("=" * 50)

try:
    print("\n1. Testing imports...")
    from modules.ai_writer import fallback_post
    from modules.facebook_publisher import publish_job
    from modules.image_maker import create_job_image
    from modules.job_tracker import get_published_count, is_job_published

    print("   OK: all modules imported successfully")
except Exception as exc:
    print(f"   FAILED: import error: {exc}")
    sys.exit(1)

print("\n2. Creating sample Arabic job...")
sample_job = {
    "title": "مهندس برمجيات",
    "company": "شركة التقنية المغربية",
    "location": "الدار البيضاء",
    "description": "نبحث عن مهندس برمجيات لديه خبرة في تطوير تطبيقات الويب.",
    "application_url": "https://example.com/job1",
    "job_type": "private",
    "remote": False,
}

print(f"   Job: {sample_job['title']}")
print(f"   Company: {sample_job['company']}")
print(f"   Location: {sample_job['location']}")

print("\n3. Checking tracker...")
if is_job_published(sample_job):
    print("   SKIP: job was already published")
else:
    print("   OK: job is new")

print("\n4. Testing post generation...")
post_data = fallback_post(sample_job)
print("   OK: post generated")
print(f"   Image title: {post_data['image_title']}")
print(f"   First comment: {post_data['first_comment']}")

print("\n5. Testing image creation...")
image_path = create_job_image(sample_job.copy(), post_data.copy())
print(f"   OK: image created at {image_path}")
print(f"   Exists: {image_path.exists()}")

print("\n6. Testing dry-run publish payload...")
result = publish_job(post_data, image_path)
print(f"   Publish result ok: {result.get('ok')}")

print("\n7. Published jobs count...")
print(f"   Total published jobs: {get_published_count()}")

print("\n" + "=" * 50)
print("System smoke test completed.")
