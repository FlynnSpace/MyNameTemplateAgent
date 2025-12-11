from tools.image import (
    text_to_image_by_kie_seedream_v4_create_task,
    image_edit_by_kie_seedream_v4_create_task,
    image_edit_by_ppio_banana_pro_create_task,
    remove_watermark_from_image_by_kie_seedream_v4_create_task
)
from tools.video import (
    text_to_video_by_kie_sora2_create_task,
    first_frame_to_video_by_kie_sora2_create_task
)
from tools.general import (
    get_task_status
)

def get_all_tools():
    """Returns the list of all available tools."""
    return [
        text_to_image_by_kie_seedream_v4_create_task,
        image_edit_by_kie_seedream_v4_create_task,
        image_edit_by_ppio_banana_pro_create_task,
        # get_task_status, # Can be optionally added or not, depending on if we want agent to call it explicitly
        text_to_video_by_kie_sora2_create_task,
        first_frame_to_video_by_kie_sora2_create_task,
        remove_watermark_from_image_by_kie_seedream_v4_create_task
    ]

