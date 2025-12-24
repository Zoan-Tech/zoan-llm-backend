from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from model.media.description import (
    MediaDescriptionRequest,
    MediaDescriptionResponse,
    MediaDescriptionTaskResponse,
)
from internal.database.media_description import (
    MediaDescriptionTaskRepository,
    TaskStatus,
)
from handler.utils import APIStatus
from action.media.description import Generator
from internal.database import get_db
from config.logging import get_logger

logger = get_logger()

router = APIRouter()

MEDIA_PREFIX = "/media"


def process_media_task(task_id: str, model: str, medias: list[str]):
    """Process media description task in background."""
    from internal.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Update status to processing
        MediaDescriptionTaskRepository.update_task_status(
            db, task_id, TaskStatus.PROCESSING
        )
        
        # Generate descriptions
        request = MediaDescriptionRequest(model=model, medias=medias)
        generator = Generator(request)
        responses = generator.generate_media_info(medias)
        
        # Convert responses to dict
        result = [resp.model_dump() for resp in responses]
        
        # Update task with result
        MediaDescriptionTaskRepository.update_task_status(
            db, task_id, TaskStatus.COMPLETED, result=result
        )
        
    except Exception as e:
        MediaDescriptionTaskRepository.update_task_status(
            db, task_id, TaskStatus.FAILED, error_message=str(e)
        )
    finally:
        db.close()


@router.post(f"{MEDIA_PREFIX}/describe")
async def media_description_generator(
    request: MediaDescriptionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Create media description task and process in background.
    Returns task ID for polling status.
    """
    # Create task in database
    task = MediaDescriptionTaskRepository.create_task(
        db=db,
        model=request.model,
        medias=request.medias
    )
    
    response_data = MediaDescriptionTaskResponse(
        task_id=task.task_id,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
    )
    # Add background task to process
    background_tasks.add_task(
        process_media_task,
        task.task_id,
        request.model,
        request.medias
    )
    
    return JSONResponse(
        status_code=202,
        content={
            "status": APIStatus.OK,
            "data": [response_data.model_dump()],
            "message": "Media description task created successfully. Use the task_id to poll for results."
        }
    )


@router.get(f"{MEDIA_PREFIX}/describe/{{task_id}}")
async def get_media_description_task(
    task_id: str,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Poll for media description task status and results.
    """
    task = MediaDescriptionTaskRepository.get_task(db, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    response_data = MediaDescriptionTaskResponse(
        task_id=task.task_id,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
    )
    
    if task.status.value == TaskStatus.COMPLETED.value and task.result:
        response_data.result = [
            MediaDescriptionResponse(**res) for res in task.result
        ]
        message = "Media description generation completed successfully"
    elif task.status.value == TaskStatus.FAILED.value:
        message = "Media description generation failed"
    elif task.status.value == TaskStatus.PROCESSING.value:
        message = "Media description generation in progress"
    else:
        message = "Media description task is pending"
    
    return JSONResponse(
        status_code=200,
        content={
            "status": APIStatus.OK,
            "data": [response_data.model_dump()],
            "message": message
        }
    )