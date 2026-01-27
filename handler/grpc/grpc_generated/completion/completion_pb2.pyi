from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ModelKwargs(_message.Message):
    __slots__ = ("temperature", "max_tokens", "top_p", "stop")
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    TOP_P_FIELD_NUMBER: _ClassVar[int]
    STOP_FIELD_NUMBER: _ClassVar[int]
    temperature: float
    max_tokens: int
    top_p: float
    stop: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, temperature: _Optional[float] = ..., max_tokens: _Optional[int] = ..., top_p: _Optional[float] = ..., stop: _Optional[_Iterable[str]] = ...) -> None: ...

class StepModuleArgs(_message.Message):
    __slots__ = ("type", "description", "value", "required", "end_user_input")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_FIELD_NUMBER: _ClassVar[int]
    END_USER_INPUT_FIELD_NUMBER: _ClassVar[int]
    type: str
    description: str
    value: str
    required: bool
    end_user_input: bool
    def __init__(self, type: _Optional[str] = ..., description: _Optional[str] = ..., value: _Optional[str] = ..., required: bool = ..., end_user_input: bool = ...) -> None: ...

class StepModule(_message.Message):
    __slots__ = ("name", "type", "description", "args", "response_mapping")
    class ArgsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: StepModuleArgs
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[StepModuleArgs, _Mapping]] = ...) -> None: ...
    class ResponseMappingEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_MAPPING_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: str
    description: str
    args: _containers.MessageMap[str, StepModuleArgs]
    response_mapping: _containers.ScalarMap[str, str]
    def __init__(self, name: _Optional[str] = ..., type: _Optional[str] = ..., description: _Optional[str] = ..., args: _Optional[_Mapping[str, StepModuleArgs]] = ..., response_mapping: _Optional[_Mapping[str, str]] = ...) -> None: ...

class AgentWorkflow(_message.Message):
    __slots__ = ("id", "name", "description", "steps")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STEPS_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    steps: _containers.RepeatedCompositeFieldContainer[StepModule]
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., steps: _Optional[_Iterable[_Union[StepModule, _Mapping]]] = ...) -> None: ...

class AgentConfig(_message.Message):
    __slots__ = ("id", "name", "model", "model_kwargs", "description", "instruction", "system_prompt", "is_enabled", "is_primary", "workflows", "stream_usage", "type", "agent_kya")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    MODEL_KWARGS_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    INSTRUCTION_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_PROMPT_FIELD_NUMBER: _ClassVar[int]
    IS_ENABLED_FIELD_NUMBER: _ClassVar[int]
    IS_PRIMARY_FIELD_NUMBER: _ClassVar[int]
    WORKFLOWS_FIELD_NUMBER: _ClassVar[int]
    STREAM_USAGE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    AGENT_KYA_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    model: str
    model_kwargs: ModelKwargs
    description: str
    instruction: str
    system_prompt: str
    is_enabled: bool
    is_primary: bool
    workflows: _containers.RepeatedCompositeFieldContainer[AgentWorkflow]
    stream_usage: bool
    type: str
    agent_kya: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., model: _Optional[str] = ..., model_kwargs: _Optional[_Union[ModelKwargs, _Mapping]] = ..., description: _Optional[str] = ..., instruction: _Optional[str] = ..., system_prompt: _Optional[str] = ..., is_enabled: bool = ..., is_primary: bool = ..., workflows: _Optional[_Iterable[_Union[AgentWorkflow, _Mapping]]] = ..., stream_usage: bool = ..., type: _Optional[str] = ..., agent_kya: _Optional[str] = ...) -> None: ...

class Attachment(_message.Message):
    __slots__ = ("url", "mime_type", "file_name", "file_size", "type")
    URL_FIELD_NUMBER: _ClassVar[int]
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    FILE_NAME_FIELD_NUMBER: _ClassVar[int]
    FILE_SIZE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    url: str
    mime_type: str
    file_name: str
    file_size: str
    type: str
    def __init__(self, url: _Optional[str] = ..., mime_type: _Optional[str] = ..., file_name: _Optional[str] = ..., file_size: _Optional[str] = ..., type: _Optional[str] = ...) -> None: ...

class Metadata(_message.Message):
    __slots__ = ("console_logs", "attachments", "web_search")
    CONSOLE_LOGS_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    WEB_SEARCH_FIELD_NUMBER: _ClassVar[int]
    console_logs: str
    attachments: _containers.RepeatedCompositeFieldContainer[Attachment]
    web_search: bool
    def __init__(self, console_logs: _Optional[str] = ..., attachments: _Optional[_Iterable[_Union[Attachment, _Mapping]]] = ..., web_search: bool = ...) -> None: ...

class CompletionRequest(_message.Message):
    __slots__ = ("user_id", "conversation_id", "message", "agents", "metadata")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    AGENTS_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    conversation_id: str
    message: str
    agents: _containers.RepeatedCompositeFieldContainer[AgentConfig]
    metadata: Metadata
    def __init__(self, user_id: _Optional[str] = ..., conversation_id: _Optional[str] = ..., message: _Optional[str] = ..., agents: _Optional[_Iterable[_Union[AgentConfig, _Mapping]]] = ..., metadata: _Optional[_Union[Metadata, _Mapping]] = ...) -> None: ...

class ChunkContent(_message.Message):
    __slots__ = ("type", "value", "agent", "index", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    TYPE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    AGENT_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    type: str
    value: str
    agent: str
    index: int
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, type: _Optional[str] = ..., value: _Optional[str] = ..., agent: _Optional[str] = ..., index: _Optional[int] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ResponseMetadata(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class StreamingChunk(_message.Message):
    __slots__ = ("content", "response_metadata")
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_METADATA_FIELD_NUMBER: _ClassVar[int]
    content: _containers.RepeatedCompositeFieldContainer[ChunkContent]
    response_metadata: ResponseMetadata
    def __init__(self, content: _Optional[_Iterable[_Union[ChunkContent, _Mapping]]] = ..., response_metadata: _Optional[_Union[ResponseMetadata, _Mapping]] = ...) -> None: ...
