import logging
import json
import time
import sys
import requests
import math
import os
import datetime
from config import config
from listToJson import save_to_json
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.serialization import StringSerializer
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka import SerializingProducer


def setup_logger():

    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    format = "%M-%S-%H_%Y-%m-%d"
    timestamp = datetime.datetime.now().strftime(format)
    log_filename = os.path.join(log_dir, f"{timestamp}_log.log")

    logging.basicConfig(
        level=logging.INFO,
        filename = log_filename,
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(message)s")
    


def  fetch_playlist_item_page(google_api_key, youtube_playlist_id, page_token=None ):
    try:
        response = requests.get("https://www.googleapis.com/youtube/v3/playlistItems",
                                params={
                                    "key":google_api_key,
                                    "part" : ["contentDetails", "id"],
                                    "playlistId":youtube_playlist_id,
                                    "pageToken" : page_token
                                })
        
        payload = response.json()
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception occurred: {e}")
        print(f"Request exception: {e}")

    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error occurred: {e}")
        print(f"JSON decode error: {e}")

    except Exception as e:
        logging.error(f"General exception occurred: {e}")
        print(f"General exception: {e}")

    logging.info("GOT PAGE:\n%s", response.text)
    return payload




def fetch_playlist_items(google_api_key, youtube_playlist_id):
    payload =  fetch_playlist_item_page(google_api_key, youtube_playlist_id)
    
    # yield from payload["items"] # this might throw Key Error
    yield from payload.get("items", [])

    next_page_token = payload.get("nextPageToken")
    while next_page_token:
        payload =  fetch_playlist_item_page(google_api_key, youtube_playlist_id, next_page_token)
        # yield from payload["items"]
        yield from payload.get("items", [])
        next_page_token = payload.get("nextPageToken")



def  fetch_video_page(google_api_key, video_id ):
    try:
        response = requests.get("https://www.googleapis.com/youtube/v3/videos",
                                params={
                                    "key":google_api_key,
                                    "part" : ["id", "snippet", "statistics"],
                                    "id":video_id
                                })
        
        payload = response.json()
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception occurred: {e}")
        print(f"Request exception: {e}")

    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error occurred: {e}")
        print(f"JSON decode error: {e}")

    except Exception as e:
        logging.error(f"General exception occurred: {e}")
        print(f"General exception: {e}")

    logging.info("GOT VIDEO PAGE ON VIDEO ID-(%s) :\n%s", video_id, response.text)
    return payload


def fetch_video_details(google_api_key, video_id):
    try:
        payload = fetch_video_page(google_api_key, video_id)
        return payload["items"][0]
    except (KeyError, IndexError) as e:
        logging.error(f"No video found for ID {video_id}: {e}")
        return None


def summarize_video_item(video):
    info = {
        "video_id": video.get("id", "Not Found"),
        "title": video.get("snippet", {}).get("title", "Not Found"),
        "view_count": video.get("statistics", {}).get("viewCount", "Not Found"),
        "like_count": video.get("statistics", {}).get("likeCount", "Not Found"),
        "comment_count": video.get("statistics", {}).get("commentCount", "Not Found"),
    }
    return info

def on_delivery(err, record):
    if err:
        print(f"Delivery failed for record {record.key()}: {err}")
        logging.info("Delivery failed for record {record.key()}: {err}")
    else:
        print(f"Record-{record.key()} was successfully delivered to {record.topic()} partition {record.partition()} at offset {record.offset()}")
        logging.info(f"Record-{record.key()} was successfully delivered to {record.topic()} partition {record.partition()} at offset {record.offset()}")

def main():

    logging_system = setup_logger()

    logging.info("X=======================================START=========================================X")
    
    schema_registry_client = SchemaRegistryClient(config["schema_registry"])
    youtube_videos_value_schema = schema_registry_client.get_latest_version("youtube_videos-value")

    kafka_config = config["kafka"] | {
        "key.serializer":StringSerializer(),
        "value.serializer":AvroSerializer(
            schema_registry_client, 
            youtube_videos_value_schema.schema.schema_str) 
    }
    producer = SerializingProducer(kafka_config)
    
    google_api_key = config["google_api_key"]
    youtube_playlist_id = config["youtube_playlist_id"]
    item_list = {"items":[]}
    count = 0
    for item in fetch_playlist_items(google_api_key, youtube_playlist_id):
        video_id = item["contentDetails"]["videoId"]

        # fetching/yielding the video details
        video = fetch_video_details(google_api_key, video_id)

        # structuring the video details
        summarized_info = summarize_video_item(video)

        item_list["items"].append(summarized_info)
        print(f"Video Recieved {count+1}: {summarized_info["title"]}")
        count+=1
        logging.info(f"Video RECEIVED {count}:\n%s", json.dumps(summarized_info, indent=4))

        value = {
            "TITLE": video.get("snippet", {}).get("title", "Not Found"),
            "VIEW_COUNT": int(video.get("statistics", {}).get("viewCount", 0)),
            "LIKE_COUNT": int(video.get("statistics", {}).get("likeCount", 0)),
            "COMMENT_COUNT": int(video.get("statistics", {}).get("commentCount", 0))
        }

    #     producer.produce(
    #         topic="youtube_videos",
    #         key=video_id,
    #         value=value,
    #         on_delivery=on_delivery
    #     )
    # producer.flush()

    logging.info("Video Information has been extracted from all the 'items' fetched from 'fetch_playlist_items' .\n")
    
    save_to_json(item_list, "items.json")


if __name__ == "__main__":
    
    sys.exit(main())