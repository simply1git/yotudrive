#!/bin/bash

echo "🔧 Setting up environment variables for YotuDrive 2.0..."

# Get Railway project variables
echo "📋 Getting Railway environment variables..."
railway variables list

echo ""
echo "🔑 Required Environment Variables:"
echo "1. YOUTUBE_API_KEY - Get from Google Cloud Console"
echo "2. GOOGLE_CLIENT_ID - Get from Google OAuth setup"
echo "3. GOOGLE_CLIENT_SECRET - Get from Google OAuth setup"
echo ""
echo "📝 To add variables, run:"
echo "railway variables set YOUTUBE_API_KEY=your_key_here"
echo "railway variables set GOOGLE_CLIENT_ID=your_client_id_here"
echo "railway variables set GOOGLE_CLIENT_SECRET=your_client_secret_here"
echo ""
echo "🌐 After setting variables, run: railway up"
