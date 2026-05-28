#!/bin/bash
set -e
cd "$(dirname "$0")/.."

# ------------------------------------------------------------------------------------------
# This script simply creates a new tag for the current version and pushes it to GitHub,
# which then triggers the GitHub Action workflow to build both Linux and Windows binaries.
# The binary folder becomes available in the Artifacts section in the workflow,
# which can be manually added to a new release on GitHub for this tag.
# ------------------------------------------------------------------------------------------

# Read version from version.py
VERSION=$(grep "__version__" version.py | sed 's/.*"\(.*\)".*/\1/')
echo "Detected version: $VERSION"


# Commit version.py
git add version.py
git commit -m "Bump version to $VERSION" || echo "No changes to commit"


# Create git tag for current version
TAG="v$VERSION"
git tag $TAG


# Push commit and tag
git push
git push origin $TAG
echo "Pushed tag $TAG"

echo "Done. GitHub Action will now trigger, building Linux and Windows binaries for $TAG."
