#!/usr/bin/env python3
"""Quick diagnostic script to check SynapseOps configuration."""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def check_env_file():
    """Check if .env file exists and has required variables."""
    print("=" * 60)
    print("1. Checking .env file...")
    print("=" * 60)
    
    if not Path(".env").exists():
        print("❌ .env file not found!")
        return False
    
    print("✅ .env file exists")
    
    required_vars = [
        "GITHUB_TOKEN",
        "GITHUB_WEBHOOK_SECRET",
        "GITHUB_REPO",
        "TEAMS_WEBHOOK_URL",
        "APP_BASE_URL",
        "AWS_REGION",
    ]
    
    from dotenv import load_dotenv
    load_dotenv()
    
    missing = []
    for var in required_vars:
        value = os.getenv(var, "")
        if not value or value == "your_webhook_secret_here" or value.startswith("your_"):
            print(f"❌ {var}: NOT SET or using placeholder")
            missing.append(var)
        else:
            # Mask sensitive values
            if "TOKEN" in var or "SECRET" in var or "WEBHOOK" in var:
                display = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display = value
            print(f"✅ {var}: {display}")
    
    return len(missing) == 0


def check_dependencies():
    """Check if required Python packages are installed."""
    print("\n" + "=" * 60)
    print("2. Checking Python dependencies...")
    print("=" * 60)
    
    required = [
        "fastapi",
        "uvicorn",
        "boto3",
        "httpx",
        "redis",
        "structlog",
        "apscheduler",
        "pydantic",
        "pydantic_settings",
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} - NOT INSTALLED")
            missing.append(pkg)
    
    if missing:
        print(f"\n⚠️  Install missing packages: pip install {' '.join(missing)}")
        return False
    
    return True


def check_server():
    """Check if server is running."""
    print("\n" + "=" * 60)
    print("3. Checking if server is running...")
    print("=" * 60)
    
    try:
        import httpx
        resp = httpx.get("http://localhost:5000/health", timeout=5)
        if resp.status_code == 200:
            print("✅ Server is running and healthy")
            print(f"   Response: {resp.json()}")
            return True
        else:
            print(f"❌ Server returned status {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server is not running or not accessible")
        print(f"   Error: {e}")
        print("\n   Start the server with: python3 app.py")
        return False


def check_aws():
    """Check AWS credentials and Bedrock access."""
    print("\n" + "=" * 60)
    print("4. Checking AWS credentials...")
    print("=" * 60)
    
    try:
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ AWS credentials configured")
        print(f"   Account: {identity['Account']}")
        print(f"   ARN: {identity['Arn']}")
        
        # Check Bedrock access
        from dotenv import load_dotenv
        load_dotenv()
        region = os.getenv("BEDROCK_REGION", "us-east-1")
        bedrock = boto3.client('bedrock-runtime', region_name=region)
        print(f"✅ Bedrock client created for region: {region}")
        
        return True
    except Exception as e:
        print(f"❌ AWS credentials issue: {e}")
        print("\n   Configure AWS: aws configure")
        return False


def check_redis():
    """Check Redis connection."""
    print("\n" + "=" * 60)
    print("5. Checking Redis connection...")
    print("=" * 60)
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        print(f"   Redis URL: {redis_url}")
        
        import redis
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis is accessible")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("\n   Start Redis: redis-server")
        print("   Or update REDIS_URL in .env")
        return False


def check_github_token():
    """Check GitHub token validity."""
    print("\n" + "=" * 60)
    print("6. Checking GitHub token...")
    print("=" * 60)
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            print("❌ GITHUB_TOKEN not set")
            return False
        
        import httpx
        resp = httpx.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            user = resp.json()
            print(f"✅ GitHub token is valid")
            print(f"   User: {user.get('login')}")
            
            # Check scopes
            scopes = resp.headers.get("X-OAuth-Scopes", "")
            print(f"   Scopes: {scopes}")
            
            if "repo" not in scopes:
                print("⚠️  Warning: 'repo' scope not found - may not work for private repos")
            
            return True
        else:
            print(f"❌ GitHub token invalid: {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ GitHub token check failed: {e}")
        return False


def check_teams_webhook():
    """Check Teams webhook URL."""
    print("\n" + "=" * 60)
    print("7. Checking Teams webhook...")
    print("=" * 60)
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        webhook_url = os.getenv("TEAMS_WEBHOOK_URL", "")
        if not webhook_url:
            print("❌ TEAMS_WEBHOOK_URL not set")
            return False
        
        print(f"   URL: {webhook_url[:50]}...")
        
        import httpx
        resp = httpx.post(
            webhook_url,
            json={"text": "SynapseOps diagnostic test"},
            timeout=10
        )
        
        if resp.status_code in (200, 202):
            print("✅ Teams webhook is accessible")
            print("   Check your Teams channel for test message")
            return True
        else:
            print(f"⚠️  Teams webhook returned status {resp.status_code}")
            print("   Webhook may be expired or invalid")
            return False
            
    except Exception as e:
        print(f"❌ Teams webhook test failed: {e}")
        return False


def print_summary(results):
    """Print summary of checks."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    checks = [
        ("Environment variables", results[0]),
        ("Python dependencies", results[1]),
        ("Server running", results[2]),
        ("AWS credentials", results[3]),
        ("Redis connection", results[4]),
        ("GitHub token", results[5]),
        ("Teams webhook", results[6]),
    ]
    
    passed = sum(1 for _, r in checks if r)
    total = len(checks)
    
    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All checks passed! Your SynapseOps setup looks good.")
        print("\nNext steps:")
        print("1. Ensure GitHub webhook is configured (see TROUBLESHOOTING.md)")
        print("2. Create a test PR to verify end-to-end flow")
        print("3. Check http://localhost:5000/activity for agent activity")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("See TROUBLESHOOTING.md for detailed help.")


def main():
    """Run all diagnostic checks."""
    print("\n🔍 SynapseOps Diagnostic Tool\n")
    
    results = [
        check_env_file(),
        check_dependencies(),
        check_server(),
        check_aws(),
        check_redis(),
        check_github_token(),
        check_teams_webhook(),
    ]
    
    print_summary(results)


if __name__ == "__main__":
    main()
