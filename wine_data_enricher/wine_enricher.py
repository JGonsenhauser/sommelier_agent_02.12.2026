import pandas as pd
import os
from datetime import datetime
from openai import OpenAI
from duckduckgo_search import DDGS
import time
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize clients
client = OpenAI()
ddgs = DDGS()

def get_business_info():
    """Prompt user for business name and ID"""
    print("\n" + "="*50)
    print("WINE DATA ENRICHMENT AGENT")
    print("="*50)
    business_name = input("Enter Business Name: ").strip()
    business_id = input("Enter Business ID: ").strip()
    return business_name, business_id

def load_input_file():
    """Load the input Excel file"""
    print("\n" + "="*50)
    print("SELECT INPUT FILE")
    print("="*50)
    file_path = input("Enter path to input .xlsx file: ").strip()
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return None
    
    try:
        df = pd.read_excel(file_path)
        print(f"\nLoaded {len(df)} wines from {os.path.basename(file_path)}")
        print(f"Columns: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"Error loading file: {e}")
        return None

def search_wine_info(wine_name, max_results=3):
    """Search DuckDuckGo for wine information"""
    try:
        results = ddgs.text(f"{wine_name} wine grape variety region tasting notes", max_results=max_results)
        return results
    except Exception as e:
        print(f"Search error for {wine_name}: {e}")
        return []

def enrich_wine_data(wine_name, wine_type, grape, region_country, tasting_note, food_pairing, price, vintage, bottle_size):
    """Use GPT to enrich incomplete wine data"""
    
    # Search for wine information
    search_results = search_wine_info(wine_name)
    search_context = "\n".join([f"- {result.get('body', '')}" for result in search_results[:3]])
    
    # Build the enrichment prompt
    prompt = f"""You are a wine expert. Based on the wine name and any existing information, complete the missing fields.
    
Wine Name: {wine_name}
Current Wine Type: {wine_type if pd.notna(wine_type) and wine_type != '' else 'Unknown'}
Current Grape: {grape if pd.notna(grape) and grape != '' else 'Unknown'}
Current Region/Country: {region_country if pd.notna(region_country) and region_country != '' else 'Unknown'}
Current Tasting Note: {tasting_note if pd.notna(tasting_note) and tasting_note != '' else 'Unknown'}
Current Food Pairing: {food_pairing if pd.notna(food_pairing) and food_pairing != '' else 'Unknown'}
Current Price: {price if pd.notna(price) and price != '' else 'Unknown'}
Current Vintage: {vintage if pd.notna(vintage) and vintage != '' else 'Unknown'}
Current Bottle Size: {bottle_size if pd.notna(bottle_size) and bottle_size != '' else 'Unknown'}

Search Results:
{search_context}

Wine Type Options: white, red, rosé, sparkling, champagne, dessert_wine

For any missing fields, provide your best answer based on wine knowledge and search results.
Return ONLY valid JSON with these exact keys (no markdown, no extra text):
{{
    "wine_type": "one of the options above",
    "grape": "primary grape variety",
    "region_country": "region, country",
    "tasting_note": "brief tasting description",
    "food_pairing": "suggested food pairing",
    "price": "estimated price or empty string",
    "vintage": "year or empty string",
    "bottle_size": "bottle size in ml or empty string"
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        # Parse response
        result_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON
        try:
            enriched = json.loads(result_text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            start = result_text.find('{')
            end = result_text.rfind('}') + 1
            if start != -1 and end > start:
                enriched = json.loads(result_text[start:end])
            else:
                enriched = {}
        
        return enriched
    except Exception as e:
        print(f"Error enriching {wine_name}: {e}")
        return {}

def process_wines(df, business_name, business_id):
    """Process all wines and enrich data"""
    print(f"\nEnriching {len(df)} wines...")
    print("This may take a minute...\n")
    
    enriched_rows = []
    
    for idx, row in df.iterrows():
        wine_name = row.get('wine_name', '')
        
        print(f"[{idx+1}/{len(df)}] Processing: {wine_name}")
        
        # Get current values
        wine_type = row.get('wine_type', '')
        grape = row.get('grape', '')
        region_country = row.get('region_country', '')
        tasting_note = row.get('tasting_note', '')
        food_pairing = row.get('food_pairing', '')
        price = row.get('price', '')
        vintage = row.get('vintage', '')
        bottle_size = row.get('bottle_size', '')
        
        # Enrich data
        enriched = enrich_wine_data(
            wine_name, wine_type, grape, region_country, 
            tasting_note, food_pairing, price, vintage, bottle_size
        )
        
        # Build enriched row with exact column order
        enriched_row = {
            'business_name': business_name,
            'business_id': business_id,
            'id': idx + 1,  # Sequential ID starting from 1
            'wine_name': wine_name,
            'wine_type': enriched.get('wine_type', wine_type or ''),
            'grape': enriched.get('grape', grape or ''),
            'region_country': enriched.get('region_country', region_country or ''),
            'tasting_note': enriched.get('tasting_note', tasting_note or ''),
            'food_pairing': enriched.get('food_pairing', food_pairing or ''),
            'price': enriched.get('price', price or ''),
            'vintage': enriched.get('vintage', vintage or ''),
            'bottle_size': enriched.get('bottle_size', bottle_size or '')
        }
        
        enriched_rows.append(enriched_row)
        
        # Rate limiting to avoid API throttling
        time.sleep(0.5)
    
    # Create output dataframe with exact column order
    column_order = [
        'business_name', 'business_id', 'id', 'wine_name', 'wine_type', 
        'grape', 'region_country', 'tasting_note', 'food_pairing', 
        'price', 'vintage', 'bottle_size'
    ]
    
    output_df = pd.DataFrame(enriched_rows)[column_order]
    return output_df

def save_output_file(df):
    """Save enriched data to output Excel file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"enriched_wines_{timestamp}.xlsx"
    output_path = os.path.join(os.path.dirname(__file__), output_filename)
    
    try:
        df.to_excel(output_path, index=False)
        print(f"\n" + "="*50)
        print(f"✓ SUCCESS!")
        print(f"Output saved to: {output_path}")
        print("="*50)
        return output_path
    except Exception as e:
        print(f"Error saving file: {e}")
        return None

def main():
    # Get business info
    business_name, business_id = get_business_info()
    
    # Load input file
    df = load_input_file()
    if df is None:
        return
    
    # Process and enrich wines
    enriched_df = process_wines(df, business_name, business_id)
    
    # Save output file
    save_output_file(enriched_df)

if __name__ == "__main__":
    main()
