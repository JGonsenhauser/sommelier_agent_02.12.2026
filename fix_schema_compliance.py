"""
Schema compliance fix for wine lists and producers.
Generates proper metadata with unified schema for Pinecone.
"""
import pandas as pd
import hashlib
from pathlib import Path
from data.schema_definitions import WineEmbedding, RestaurantWineEmbedding

def generate_text_for_embedding(producer, label, grapes, region, major_region, country):
    """Generate standardized text for embedding per schema."""
    return f"Producer: {producer} | Label: {label or ''} | Grapes: {grapes} | Region: {region} | Major Region: {major_region or region} | Country: {country}"

def fix_maass_wine_list():
    """Fix MAASS wine list CSV to match schema."""
    print("\n=== FIXING MAASS WINE LIST ===")
    df = pd.read_csv('data/raw/maass_wine_list.csv')
    
    # Rename columns to match schema
    df['label'] = df['wine_name']
    df['major_region'] = df['region']  # Use region as major_region (can be updated later)
    df['text'] = df.apply(
        lambda row: generate_text_for_embedding(
            row['producer'],
            row.get('label', ''),
            row['grapes'],
            row['region'],
            row.get('major_region'),
            row['country']
        ),
        axis=1
    )
    
    # Add restaurant-specific fields
    df['price_range'] = df['price'].apply(categorize_price)
    df['tasting_keywords'] = df['tasting_note'].fillna('No tasting note provided.')
    df['list_id'] = 'maass_wine_list'
    df['qr_id'] = 'qr_maass'
    df['restaurant'] = 'maass'
    
    # Select only schema-compliant columns
    schema_cols = [
        'producer', 'label', 'grapes', 'region', 'major_region', 'country',
        'text', 'price_range', 'price', 'tasting_keywords', 'list_id', 'qr_id',
        'restaurant'
    ]
    df_fixed = df[[col for col in schema_cols if col in df.columns]].copy()
    
    output = 'data/raw/maass_wine_list_schema_compliant.csv'
    df_fixed.to_csv(output, index=False)
    print(f"✓ Fixed MAASS list saved to {output}")
    print(f"  Rows: {len(df_fixed)}")
    print(f"  Columns: {list(df_fixed.columns)}")
    return df_fixed

def fix_producer_list():
    """Fix producer list XLSX to match schema."""
    print("\n=== FIXING PRODUCER LIST ===")
    df = pd.read_excel('wine_producer_scaper/producer_list_organized.xlsx')
    
    # Generate embedding text
    df['text'] = df.apply(
        lambda row: generate_text_for_embedding(
            row['producer'],
            row.get('label', ''),
            row['grapes'],
            row['region'],
            row.get('major_region'),
            row['country']
        ),
        axis=1
    )
    
    # Add missing optional fields
    if 'label' not in df.columns:
        df['label'] = ''
    if 'major_region' not in df.columns:
        df['major_region'] = df['region']
    
    # Master namespace fields only
    master_cols = ['producer', 'label', 'grapes', 'region', 'major_region', 'country', 'text']
    df_fixed = df[[col for col in master_cols if col in df.columns]].copy()
    
    output = 'wine_producer_scaper/producer_list_schema_compliant.xlsx'
    df_fixed.to_excel(output, index=False)
    print(f"✓ Fixed producer list saved to {output}")
    print(f"  Rows: {len(df_fixed)}")
    print(f"  Columns: {list(df_fixed.columns)}")
    return df_fixed

def categorize_price(price):
    """Categorize price into range buckets."""
    if pd.isna(price) or price == 0:
        return "<$50"
    if price < 50:
        return "<$50"
    elif price < 100:
        return "$50–$100"
    elif price < 200:
        return "$100–$200"
    else:
        return "$200+"

def generate_master_vector_id(producer, label, grapes, region, country):
    """Generate deterministic master vector ID (MD5 hash)."""
    text = f"{producer}_{label or ''}_{grapes}_{region}_{country}"
    return hashlib.md5(text.encode()).hexdigest()

def check_schema_compliance():
    """Verify schema compliance after fixes."""
    print("\n=== SCHEMA COMPLIANCE VERIFICATION ===\n")
    
    maass_df = pd.read_csv('data/raw/maass_wine_list_schema_compliant.csv')
    producer_df = pd.read_excel('wine_producer_scaper/producer_list_schema_compliant.xlsx')
    
    required_core = {'producer', 'label', 'grapes', 'region', 'major_region', 'country', 'text'}
    required_restaurant = {'price_range', 'tasting_keywords', 'list_id', 'qr_id', 'restaurant'}
    
    maass_cols = set(maass_df.columns)
    producer_cols = set(producer_df.columns)
    
    print("MAASS WINE LIST:")
    core_ok = required_core.issubset(maass_cols)
    restaurant_ok = required_restaurant.issubset(maass_cols)
    print(f"  ✓ Core fields present: {core_ok}")
    print(f"  ✓ Restaurant fields present: {restaurant_ok}")
    print(f"  Columns: {sorted(list(maass_cols))}\n")
    
    print("PRODUCER LIST (Master Namespace):")
    producer_core_ok = required_core.issubset(producer_cols)
    print(f"  ✓ Core fields present: {producer_core_ok}")
    print(f"  (Restaurant fields not required for master)")
    print(f"  Columns: {sorted(list(producer_cols))}\n")
    
    if core_ok and restaurant_ok and producer_core_ok:
        print("✓ ALL SCHEMAS COMPLIANT!")
        return True
    else:
        print("✗ Schema issues remain")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("WINE DATA SCHEMA COMPLIANCE FIX")
    print("=" * 80)
    
    maass_fixed = fix_maass_wine_list()
    producer_fixed = fix_producer_list()
    
    compliance_ok = check_schema_compliance()
    
    print("\n" + "=" * 80)
    if compliance_ok:
        print("✓ Schema compliance fixes complete!")
        print("  Next: Re-embed fixed data to Pinecone")
    else:
        print("✗ Manual review needed")
    print("=" * 80)
