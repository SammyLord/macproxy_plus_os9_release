# HINT: "NOT Youtube" is not associated with or endorsed by YouTube, and does not connect to or otherwise interact with YouTube in any way.

import os
import json
import random
import string
import subprocess
from flask import request, send_file, render_template_string
from urllib.parse import urlparse, parse_qs
import yt_dlp
import config

DOMAIN = "youtube.com"
EXTENSION_DIR = os.path.dirname(os.path.abspath(__file__))
FLIM_DIRECTORY = os.path.join(EXTENSION_DIR, "flims")
DOWNLOAD_DIRECTORY = os.path.join(EXTENSION_DIR, "downloads")
PROFILE = "plus"

# Ensure directories exist
os.makedirs(FLIM_DIRECTORY, exist_ok=True)
os.makedirs(DOWNLOAD_DIRECTORY, exist_ok=True)

def generate_homepage():
	return render_template_string('''
	<!DOCTYPE html>
	<html lang="en">
		<head>
			<meta charset="UTF-8">
			<title>Yeah! YouTube - Broadcast Yourself</title>
		</head>
		<body>
			<center>
<pre>
                                                   
  ##      ##         ########     ##               
   ##    ##             ##        ##               
    ##  ## ####  ##  ## ## ##  ## #####   ####     
     #### ##  ## ##  ## ## ##  ## ##  ## ##  ##    
      ##  ##  ## ##  ## ## ##  ## ##  ## ######    
      ##  ##  ## ##  ## ## ##  ## ##  ## ##        
YEAH! ##   ####   ##### ##  ##### #####   #####    
<br>
</pre>
				<form method="get" action="/results">
					<input type="text" size="40" name="search_query" required style="font-size: 42px;">
					<input type="submit" value="Search">
				</form>
				<br>
			</center>
			<hr>
		</body>
	</html>
	''')

def generate_search_results(search_results, query):
	videos_html = generate_search_results_html(search_results)
	return render_template_string('''
	<!DOCTYPE html>
	<html lang="en">
		<head>
			<meta charset="UTF-8">
			<title>Yeah! YouTube - Search Results for {{ query }}</title>
		</head>
		<body>
			<form method="get" action="/results">
				<input type="text" size="40" name="search_query" value="{{ query }}" required style="font-size: 16px;">
				<input type="submit" value="Search">
			</form>
			<hr>
			{{ videos_html|safe }}
		</body>
	</html>
	''', videos_html=videos_html, query=query)

def generate_search_results_html(videos):
	html = ''
	for video in videos:
		video_id = video.get('id')
		if not video_id:
			continue
		url = f"https://www.{DOMAIN}/watch?v={video_id}"
		title = video.get('title', 'Untitled')
		creator = video.get('uploader', 'Unknown creator')
		description = video.get('description', '')

		# Handle description formatting
		if description:
			if len(description) > 200:
				formatted_description = f"{description[:200]}..."
			else:
				formatted_description = description
		else:
			formatted_description = "..."

		html += f'''
		<b><a href="{url}">{title}</a></b><br>
		<font size="2">
			<b>{creator}</b><br>
			{formatted_description}
		</font>
		<br><br>
		'''
	return html

def handle_video_request(video_id):
	# Download the video using yt-dlp
	video_url = f"https://www.youtube.com/watch?v={video_id}"
	
	ydl_opts = {
		'format': 'worst',
		'outtmpl': os.path.join(DOWNLOAD_DIRECTORY, f"{video_id}.%(ext)s"),
		'noplaylist': True,
		'quiet': True,
		'no_warnings': True,
	}

	downloaded_video_path = None
	with yt_dlp.YoutubeDL(ydl_opts) as ydl:
		try:
			info_dict = ydl.extract_info(video_url, download=True)
			downloaded_video_path = ydl.prepare_filename(info_dict)
		except Exception as e:
			print(f"Error downloading video: {e}")
			return "Error downloading video", 500
			
	if not downloaded_video_path or not os.path.exists(downloaded_video_path):
		return "Error: Failed to download video", 500

	flim_path = os.path.join(FLIM_DIRECTORY, f"{video_id}.mov")
	
	try:
		subprocess.run([
			"ffmpeg",
			"-n", # dont overwrite output file if it exists
			"-i", downloaded_video_path,
			"-f", "mov",
			"-vcodec", "svq1",  # Sorenson Video codec (better Mac OS 9 compatibility)
			"-acodec", "adpcm_ima_qt",  # ADPCM audio (better Mac OS 9 compatibility)
			"-ar", "11025",  # Lower audio sample rate
			"-ac", "1",  # Mono audio
			"-vf", "scale=300:225",  # Lower resolution for Mac OS 9
			"-r", "12",  # Lower frame rate for 56k
			"-b:v", "74k",  # Very low bitrate for 56k
			"-b:a", "4k",  # Low audio bitrate
			"-q:v", "5",  # Slightly lower quality
			flim_path
		], check=True, capture_output=True, text=True)
	except subprocess.CalledProcessError as e:
		print(f"ffmpeg error: {e.stderr}")
		return "Error generating video", 500
	finally:
		# Clean up the downloaded file
		if os.path.exists(downloaded_video_path):
			os.remove(downloaded_video_path)

	if os.path.exists(flim_path):
		return send_file(flim_path, as_attachment=True, download_name=f"{video_id}.mov")
	else:
		return "Error: File not generated", 500

def search_videos(query):
	ydl_opts = {
		'quiet': True,
		'default_search': 'ytsearch10',  # search for 10 videos
		'noplaylist': True,
	}
	with yt_dlp.YoutubeDL(ydl_opts) as ydl:
		try:
			search_results = ydl.extract_info(query, download=False)
			return search_results.get('entries', [])
		except Exception as e:
			print(f"Error searching youtube: {e}")
			return []

def handle_request(req):
	parsed_url = urlparse(req.url)
	path = parsed_url.path
	query_params = parse_qs(parsed_url.query)

	if path == "/watch" and 'v' in query_params:
		video_id = query_params['v'][0]
		return handle_video_request(video_id)
	elif path == "/results" and 'search_query' in query_params:
		query = query_params['search_query'][0]
		search_results = search_videos(query)
		return generate_search_results(search_results, query), 200
	else:
		return generate_homepage(), 200
