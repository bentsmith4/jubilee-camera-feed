"""Owner-approved equal publication policy for all six Jubilee cameras."""
CAMERAS = (
    ('montrose_pier_boat', 'Montrose Boat Camera'),
    ('montrose_pier_bird', 'Montrose Pier Bird Camera'),
    ('montrose_shoreline', 'Montrose Looking at Beach Camera'),
    ('pcl_e2_back_deck', 'Point Clear E2 Deck'),
    ('pcl_e2_bay_mouth', 'Point Clear E2 Down the Marina'),
    ('pcl_e3_bay_mouth', 'Point Clear Landing House Deck'),
)
CAMERA_IDS = tuple(camera_id for camera_id, _label in CAMERAS)
