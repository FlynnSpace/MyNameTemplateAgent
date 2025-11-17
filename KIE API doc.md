# Response Example
{
  "code": 200,
  "message": "success",
  "data": {
    "taskId": "task_12345678",
    "model": "sora-2-text-to-video",
    "state": "success",
    "param": "{\"model\":\"sora-2-text-to-video\",\"callBackUrl\":\"https://your-domain.com/api/callback\",\"input\":{\"prompt\":\"A professor stands at the front of a lively classroom, enthusiastically giving a lecture. On the blackboard behind him are colorful chalk diagrams. With an animated gesture, he declares to the students: “Sora 2 is now available on Kie AI, making it easier than ever to create stunning videos.” The students listen attentively, some smiling and taking notes.\",\"aspect_ratio\":\"landscape\",\"n_frames\":\"10\",\"remove_watermark\":true}}",
    "resultJson": "{\"resultUrls\":[\"https://example.com/generated-image.jpg\"],\"resultWaterMarkUrls\":[\"https://example.com/generated-watermark-image.jpg\"]}",
    "failCode": "",
    "failMsg": "",
    "completeTime": 1698765432000,
    "createTime": 1698765400000,
    "updateTime": 1698765432000
  }
}

# Response Fields

code
Status code, 200 for success, others for failure
message
Response message, error description when failed
data.taskId
Task ID
data.model
Model used for generation
data.state
Generation state
data.param
Complete Create Task request parameters as JSON string (includes model, callBackUrl, input and all other parameters)
data.resultJson
Result JSON string containing generated media URLs
data.failCode
Error code (when generation failed)
data.failMsg
Error message (when generation failed)
data.completeTime
Completion timestamp
data.createTime
Creation timestamp
data.updateTime
Update timestamp

State Values
waiting
Waiting for generation
queuing
In queue
generating
Generating
success
Generation successful
fail
Generation failed
