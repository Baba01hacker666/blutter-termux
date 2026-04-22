#!/data/data/com.termux/files/usr/bin/bash

# Update packages
pkg update -y

# Install dependencies
pkg install -y git cmake ninja build-essential pkg-config libicu capstone fmt python

# Install python dependencies
pip install requests pyelftools

echo "Environment setup complete!"
echo "If you face errors related to 'no member named format', run the following command:"
echo "find . -type f -name '*.cpp' -o -name '*.h' | xargs sed -i 's/std::format/fmt::format/g'"
