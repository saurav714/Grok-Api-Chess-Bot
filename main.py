import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Ensure the logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [Chess Bot] %(message)s',
    handlers=[
        RotatingFileHandler(
            'logs/chess_bot.log',
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def setup_environment():
    """Setup environment and verify requirements"""
    try:
        # Load environment variables from .env
        load_dotenv()
        
        # Verify GROK_API_KEY is set
        if not os.getenv('GROK_API_KEY'):
            logger.error("GROK_API_KEY not found in .env file")
            print("Error: Please set GROK_API_KEY in .env file")
            sys.exit(1)
            
        # Add src directory to Python path
        src_path = os.path.join(os.path.dirname(__file__), 'src')
        if src_path not in sys.path:
            sys.path.append(src_path)
            
        logger.info("Environment setup completed")
        return True
        
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        print(f"Error during setup: {e}")
        return False

def main():
    """Main entry point for the chess bot"""
    try:
        if not setup_environment():
            sys.exit(1)
            
        # Import gui module after environment setup
        from src.gui import main as gui_main
        
        logger.info("Starting Chess Bot application")
        gui_main()
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        print("\nApplication stopped by user")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()