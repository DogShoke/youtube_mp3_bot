import asyncio
import os
from downloader import download_youtube_audio

async def test():
    url = "https://www.youtube.com/watch?v=g3jCAyPai2Y"
    print("Downloading test video...")
    try:
        result = await download_youtube_audio(url)
        print("Success! Download results:")
        print(f"Path: {result['file_path']}")
        print(f"Title: {result['title']}")
        print(f"Artist: {result['artist']}")
        print(f"Size: {result['file_size']} bytes")
        print(f"Duration: {result['duration']} sec")
        
        if os.path.exists(result['file_path']):
            print("File exists on disk.")
            os.remove(result['file_path'])
            print("Cleaned up successfully.")
        else:
            print("Error: file does not exist!")
    except Exception as e:
        print(f"Error during download test: {e}")

if __name__ == "__main__":
    asyncio.run(test())
