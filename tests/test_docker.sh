#!/bin/bash
set -e

# Setup environment variables for auth
export WEBLINT_USERNAME=admin
export WEBLINT_PASSWORD=adminpass
export SECRET_KEY=test-secret-key

# Backup original docker-compose.yml
cp docker-compose.yml docker-compose.yml.bak

# Modify docker-compose.yml to build from source
sed -i 's|image: ghcr.io/photoncody/weblint:latest|# image: ghcr.io/photoncody/weblint:latest|g' docker-compose.yml
sed -i 's|# build: \.|build: .|g' docker-compose.yml

# Enable authentication in docker-compose.yml so we can test the auth flow
sed -i 's|# - WEBLINT_USERNAME=admin|- WEBLINT_USERNAME=${WEBLINT_USERNAME}|g' docker-compose.yml
sed -i 's|# - WEBLINT_PASSWORD=password|- WEBLINT_PASSWORD=${WEBLINT_PASSWORD}|g' docker-compose.yml

# Cleanup function to ensure we teardown the container and restore compose file
cleanup() {
    echo "Cleaning up..."
    docker compose down -v || docker-compose down -v || true
    mv docker-compose.yml.bak docker-compose.yml
    rm -f cookies.txt
}
trap cleanup EXIT

# Build and start container
echo "Building and starting Docker container..."
docker compose build || docker-compose build
docker compose up -d || docker-compose up -d

# Wait for the container to start
echo "Waiting for service to start..."
sleep 5
# Wait up to 30 seconds for the service to respond
for i in {1..10}; do
    if curl -s http://localhost:5000 > /dev/null; then
        echo "Service is up!"
        break
    fi
    echo "Waiting..."
    sleep 3
done

BASE_URL="http://localhost:5000"
COOKIE_JAR="cookies.txt"

# Test 1: Unauthenticated access redirects to login
echo "Test 1: Unauthenticated access redirects to login..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
if [ "$STATUS" != "302" ]; then
    echo "Failed: Expected 302, got $STATUS"
    exit 1
fi
LOCATION=$(curl -s -D - -o /dev/null "$BASE_URL/" | grep -i Location)
if [[ "$LOCATION" != *"/login"* ]]; then
    echo "Failed: Redirect location does not contain /login. Location: $LOCATION"
    exit 1
fi
echo "Pass"

# Test 2: Login and store session cookies
echo "Test 2: Login and store session cookies..."
# Perform login
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    -d "username=admin" -d "password=adminpass" \
    "$BASE_URL/login")
if [ "$STATUS" != "302" ]; then
    echo "Failed: Expected 302 redirect after login, got $STATUS"
    exit 1
fi
echo "Pass"

# Test 3: Verify authenticated access to index
echo "Test 3: Verify authenticated access to index..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE_URL/")
if [ "$STATUS" != "200" ]; then
    echo "Failed: Expected 200, got $STATUS"
    exit 1
fi
CONTENT=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/")
if [[ "$CONTENT" != *"WebLint"* ]]; then
    echo "Failed: Index page doesn't contain 'WebLint'"
    exit 1
fi
echo "Pass"

# Test 4: Create a snippet
echo "Test 4: Create a snippet..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" \
    -d "title=Docker Test Snippet" \
    -d "content=This is a test from docker script" \
    -d "type=plain" \
    -d "parsing_mode=weblint" \
    -d "notes=Test notes" \
    "$BASE_URL/new")

if [ "$STATUS" != "302" ]; then
    echo "Failed: Expected 302 after creating snippet, got $STATUS"
    exit 1
fi

# Verify it exists on index
CONTENT=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/")
if [[ "$CONTENT" != *"Docker Test Snippet"* ]]; then
    echo "Failed: Created snippet not found on index"
    exit 1
fi

# Extract snippet ID
SNIPPET_ID=$(echo "$CONTENT" | grep -o 'href="/view/[^"]*"' | head -n 1 | awk -F'/' '{print $3}' | cut -d'"' -f1)

if [ -z "$SNIPPET_ID" ]; then
    echo "Failed: Could not extract snippet ID"
    exit 1
fi
echo "Pass (Snippet ID: $SNIPPET_ID)"

# Test 5: View the created snippet
echo "Test 5: View the created snippet..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE_URL/view/$SNIPPET_ID")
if [ "$STATUS" != "200" ]; then
    echo "Failed: Expected 200 viewing snippet, got $STATUS"
    exit 1
fi
VIEW_CONTENT=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/view/$SNIPPET_ID")
if [[ "$VIEW_CONTENT" != *"Docker Test Snippet"* ]]; then
    echo "Failed: Snippet content not found in view"
    exit 1
fi
echo "Pass"

# Test 6: Delete the snippet
echo "Test 6: Delete the snippet..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE_URL/delete/$SNIPPET_ID")
if [ "$STATUS" != "302" ]; then
    echo "Failed: Expected 302 after deleting snippet, got $STATUS"
    exit 1
fi

# Verify it's gone
CONTENT=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/")
if [[ "$CONTENT" == *"Docker Test Snippet"* ]]; then
    echo "Failed: Snippet still found on index after deletion"
    exit 1
fi
echo "Pass"

echo "All tests passed successfully!"
