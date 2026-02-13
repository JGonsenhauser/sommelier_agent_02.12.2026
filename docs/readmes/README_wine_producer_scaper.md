# Wine Producer Top 50 Worldwide List

A comprehensive, organized dataset of premium wine producers from around the world, organized by region and country of origin.

## Overview

This repository contains a curated list of top wine producers sourced from `list_producers_raw.xlsx`, processed and organized into a clean, structured format for easy reference and analysis.

### Dataset Summary

- **Total Producer Entries**: 602
- **Unique Producers**: 546
- **Wine Regions**: 14
- **Countries Represented**: 6

## Geographic Breakdown

### By Country

| Country | Producers | Regions |
|---------|-----------|---------|
| 🇦🇺 Australia | 156 | 2 |
| 🇺🇸 United States | 146 | 1 |
| 🇫🇷 France | 130 | 5 |
| 🇩🇪 Germany | 79 | 3 |
| 🇳🇿 New Zealand | 51 | 1 |
| 🇪🇸 Spain | 40 | 2 |

### By Region

- **Australia**: Barossa Valley, Yarra Valley
- **United States**: Sonoma
- **France**: Bordeaux, Burgundy, Champagne, Loire Valley, Alsace
- **Germany**: Mosel, Rheingau, Pfalz
- **New Zealand**: Marlborough
- **Spain**: Rioja, Priorat

## Data Structure

The organized dataset (`producer_list_organized.xlsx`) includes the following columns:

| Column | Description |
|--------|-------------|
| `producer` | Name of the wine producer |
| `label` | Notable wines and styles produced |
| `grapes` | Grape varieties (available for future updates) |
| `region` | Wine region of origin |
| `country` | Country of origin |

## Data Processing

The raw data was processed to:

1. **Parse multiple producers** from single cells (comma-separated values)
2. **Organize by region and country** for geographical grouping
3. **Remove duplicates** while preserving diverse wine styles
4. **Create a standardized format** with consistent column structure

## Files

- **`list_producers_raw.xlsx`** - Original raw data file
- **`producer_list_organized.xlsx`** - Processed and organized dataset (recommended for use)
- **`README.md`** - This file

## Usage

The organized dataset is sorted alphabetically by country, region, and producer name. This makes it easy to:

- Filter by geographic location
- Identify producers by wine style
- Research specific regions
- Build wine collections by country or region

## Data Quality

- Entries are sorted for easy navigation
- Duplicates removed while maintaining data integrity
- All producers verified to be associated with their listed regions
- Notable wine styles and labels included where available

## Future Enhancements

Potential areas for expansion:

- Add specific grape variety information
- Include wine ratings/scores
- Add producer website/contact information
- Expand to additional regions and countries
- Include vintage recommendations

## License

This dataset is provided for reference and research purposes.

## Contributing

If you have updates, corrections, or additions to this wine producer list, please feel free to contribute!

---

**Last Updated**: January 26, 2026

**Source**: Comprehensive worldwide wine producer database organized by region and country.
