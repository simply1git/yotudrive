# Video Configuration
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30

# Encoding Configuration
DEFAULT_BLOCK_SIZE = 2  # Default size of each "pixel" block (2x2 pixels represent 1 bit)
MAX_BLOCK_SIZE = 15     # Max block size to ensure 1024-byte header fits in one frame (1920*1080/16^2 = 8100 bits < 8192)
DEFAULT_HEADER_COPIES = 5 # Number of times to repeat the header frame for robustness

# Calculate effective data resolution (based on DEFAULT_BLOCK_SIZE for now)
DATA_WIDTH = VIDEO_WIDTH // DEFAULT_BLOCK_SIZE
DATA_HEIGHT = VIDEO_HEIGHT // DEFAULT_BLOCK_SIZE
BITS_PER_FRAME = DATA_WIDTH * DATA_HEIGHT
BYTES_PER_FRAME = BITS_PER_FRAME // 8

# Reed-Solomon / ECC Configuration
DEFAULT_ECC_BYTES = 32
RS_BLOCK_SIZE = 255
# DATA_BLOCK_SIZE will be calculated dynamically based on ECC_BYTES
CHUNK_SIZE = (RS_BLOCK_SIZE - DEFAULT_ECC_BYTES) * 1024 

# Color Configuration
COLOR_0 = (0, 0, 0)      # Black for bit 0
COLOR_1 = (255, 255, 255) # White for bit 1

# Metadata Header Size (in bytes) to store file info at start of video
HEADER_SIZE = 1024 
