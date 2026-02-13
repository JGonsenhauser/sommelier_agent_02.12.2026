"""
QR Code generator for restaurant wine list access.
Each QR code links to a restaurant-specific sommelier interface.
"""
import qrcode
from pathlib import Path
from typing import Optional
import logging

from restaurants.restaurant_config import RestaurantConfig

logger = logging.getLogger(__name__)


class RestaurantQRGenerator:
    """Generate QR codes for restaurant wine list access."""

    def __init__(self, base_url: str = "http://localhost:8501"):
        """
        Initialize QR generator.

        Args:
            base_url: Base URL for the sommelier app (e.g., your deployment URL)
        """
        self.base_url = base_url.rstrip("/")

    def generate_qr_code(
        self,
        config: RestaurantConfig,
        output_path: Optional[Path] = None,
        size: int = 300
    ) -> Path:
        """
        Generate QR code for a restaurant.

        Args:
            config: Restaurant configuration
            output_path: Where to save the QR code (defaults to config path)
            size: QR code size in pixels

        Returns:
            Path to generated QR code
        """
        # Build URL with restaurant ID parameter
        url = f"{self.base_url}/?restaurant={config.restaurant_id}"

        # Create QR code
        qr = qrcode.QRCode(
            version=1,  # Size: 1 is 21x21, scales automatically
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
            box_size=10,
            border=4,
        )

        qr.add_data(url)
        qr.make(fit=True)

        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")

        # Save to file
        if output_path is None:
            output_path = config.qr_code_path

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path))

        logger.info(f"Generated QR code for {config.name} at {output_path}")
        logger.info(f"QR code URL: {url}")

        return output_path

    def generate_styled_qr_code(
        self,
        config: RestaurantConfig,
        logo_path: Optional[Path] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Generate a styled QR code with optional logo overlay.

        Args:
            config: Restaurant configuration
            logo_path: Optional path to restaurant logo
            output_path: Where to save the QR code

        Returns:
            Path to generated QR code
        """
        from PIL import Image, ImageDraw

        # Build URL
        url = f"{self.base_url}/?restaurant={config.restaurant_id}"

        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )

        qr.add_data(url)
        qr.make(fit=True)

        # Generate base image
        img = qr.make_image(fill_color=config.primary_color, back_color="white").convert('RGB')

        # Add logo if provided
        if logo_path and logo_path.exists():
            logo = Image.open(logo_path)

            # Calculate logo size (15% of QR code size)
            qr_width, qr_height = img.size
            logo_size = int(qr_width * 0.15)

            # Resize logo
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

            # Calculate position (center)
            logo_pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)

            # Create white background for logo
            logo_bg = Image.new('RGB', (logo_size + 20, logo_size + 20), 'white')
            logo_bg.paste(logo, (10, 10))

            # Paste logo onto QR code
            img.paste(logo_bg, (logo_pos[0] - 10, logo_pos[1] - 10))

        # Save
        if output_path is None:
            output_path = config.qr_code_path

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path))

        logger.info(f"Generated styled QR code for {config.name} at {output_path}")
        return output_path


def generate_all_restaurant_qr_codes(base_url: str = "http://localhost:8501"):
    """Generate QR codes for all configured restaurants."""
    from restaurants.restaurant_config import get_restaurant_config

    generator = RestaurantQRGenerator(base_url=base_url)

    # Generate for MAASS
    maass_config = get_restaurant_config("maass")
    if maass_config:
        generator.generate_qr_code(maass_config)
        print(f"✓ Generated QR code for {maass_config.name}")
        print(f"  Path: {maass_config.qr_code_path}")
        print(f"  Scan with your phone to access the wine list!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # For local testing
    generate_all_restaurant_qr_codes(base_url="http://localhost:8501")

    # For production, use your deployed URL:
    # generate_all_restaurant_qr_codes(base_url="https://your-domain.com")
