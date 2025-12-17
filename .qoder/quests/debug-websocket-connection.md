# Debug WebSocket Connection Issue

## Problem Statement

The worker successfully connects to the Reflex WebSocket server at `ws://localhost:8000/ws/heartbeat` but experiences premature connection termination with the error:

```
ConnectionResetError: [WinError 64] The specified network name is no longer available
websockets.exceptions.ConnectionClosedError: no close frame received or sent
```

The connection drops approximately 6 minutes after establishment (23:03:19 connected, 23:09:06 disconnected), and the worker automatically reconnects but then disconnects again.

## Root Cause Analysis

### Primary Issue: Unacknowledged Messages on Server Side

The server-side websocket handler (`websocket_server.py`) only sends acknowledgment responses for specific message types:
- `worker_register`: Sends ACK
- `heartbeat`: Sends ACK
- Other message types (`event`, `job_started`): No response sent

However, the worker sends event messages like `job_started` without receiving any acknowledgment, which may cause the underlying WebSocket protocol to consider the connection unhealthy.

### Secondary Issue: No Keepalive Mechanism

The worker sends heartbeats every 60 seconds, but there is no explicit WebSocket-level keepalive (ping/pong) mechanism. On Windows with certain network configurations, idle connections may be terminated by the OS or network stack if no bidirectional traffic occurs.

### Tertiary Issue: Exception Handling Masks Root Cause

Both worker and server use `logger.exception()` for connection errors, which prints full stack traces even for expected disconnections. This makes it harder to identify the actual issue versus normal reconnection behavior.

## Solution Design

### 1. Server-Side WebSocket Improvements

#### 1.1 Acknowledge All Message Types

Modify the `websocket_endpoint` function in `websocket_server.py` to send acknowledgments for all received messages, not just registration and heartbeat.

**Current Behavior:**
- `worker_register` → ACK sent
- `heartbeat` → ACK sent
- `event` → No ACK
- `job_result` → No ACK

**Target Behavior:**
- All message types receive acknowledgment
- This ensures bidirectional communication and prevents protocol-level timeouts

**Implementation Strategy:**
- Add a default ACK response at the end of the message processing block
- Use conditional logic to avoid duplicate ACKs for messages that already receive specific responses

#### 1.2 Add WebSocket Ping/Pong Keepalive

Enhance the server to send periodic ping frames to maintain connection health independent of application-level heartbeats.

**Rationale:**
- Application heartbeats (60s interval) are for worker status tracking
- WebSocket pings (20-30s interval) are for connection health verification
- Pings are handled at the protocol layer and don't interfere with application messages

**Implementation Strategy:**
- Create a background task that sends ping frames to all connected workers
- Use `websocket.send_text()` with a lightweight ping message or rely on WebSocket protocol-level pings
- Configure a shorter interval (20-30 seconds) to prevent Windows network stack timeouts

### 2. Worker-Side Connection Resilience

#### 2.1 Add Connection Configuration

Configure the `websockets.connect()` call with appropriate timeout and keepalive parameters.

**Configuration Parameters:**
- `ping_interval`: 20 seconds (send ping every 20s)
- `ping_timeout`: 10 seconds (wait max 10s for pong response)
- `close_timeout`: 5 seconds (graceful shutdown timeout)

**Rationale:**
These settings ensure the WebSocket library actively monitors connection health at the protocol level, independent of application-level heartbeats.

#### 2.2 Improve Error Logging Clarity

Differentiate between expected reconnections and unexpected errors.

**Current Behavior:**
All exceptions logged with full stack traces using `logger.exception()`

**Target Behavior:**
- Expected disconnections (ConnectionClosed during normal operation): Info or Warning level
- Network errors during reconnect attempts: Debug or Info level
- Unexpected errors: Error level with stack trace

**Implementation Strategy:**
- Use `logger.info()` or `logger.warning()` for graceful disconnections
- Reserve `logger.exception()` for truly unexpected errors
- Add contextual messages to help operators understand if action is required

### 3. Message Flow Enhancement

#### 3.1 Ensure Bidirectional Message Flow

Every message sent from worker to server should receive some form of acknowledgment to maintain healthy bidirectional communication.

**Message Flow Table:**

| Worker → Server | Server Response | Purpose |
|----------------|-----------------|---------|
| `worker_register` | `{"type": "ack", "msg": "registered"}` | Registration confirmation |
| `heartbeat` | `{"type": "ack", "received": true}` | Heartbeat acknowledgment |
| `job_started` | `{"type": "ack", "received": true}` | Event acknowledgment |
| `job_result` | `{"type": "ack", "received": true}` | Result received confirmation |

#### 3.2 Optional: Add Heartbeat ACK Validation

Enhance the worker to track whether heartbeat ACKs are received, and log warnings if ACKs are missing.

**Implementation Strategy:**
- Track the last ACK timestamp
- Compare with last sent heartbeat timestamp
- If no ACK received within expected time (e.g., 90 seconds), log a warning
- This is for monitoring purposes only; the connection will self-heal via reconnect logic

### 4. Testing Strategy

#### 4.1 Connection Stability Test

**Test Procedure:**
1. Start the Reflex server
2. Start the worker
3. Monitor connection for 15 minutes without job execution
4. Verify no disconnections occur during idle period

**Success Criteria:**
- Worker remains connected for entire duration
- Heartbeats continue transmitting every 60 seconds
- No ConnectionResetError or ConnectionClosedError in logs

#### 4.2 Job Execution During Active Connection

**Test Procedure:**
1. Establish worker connection
2. Schedule and trigger test_job.py execution
3. Verify job executes successfully
4. Verify worker remains connected after job completion
5. Schedule multiple jobs in sequence (5-10 jobs)

**Success Criteria:**
- All jobs execute successfully
- Worker connection remains stable throughout
- Job results are recorded in database
- No connection errors during or after execution

#### 4.3 Network Resilience Test

**Test Procedure:**
1. Establish worker connection
2. Simulate temporary network disruption (pause Reflex server for 10 seconds, then resume)
3. Verify worker automatically reconnects
4. Verify normal operation resumes after reconnection

**Success Criteria:**
- Worker detects disconnection within ping_timeout period
- Worker automatically reconnects within retry_delay period
- Reconnection is successful and stable
- Subsequent jobs can be executed normally

## Implementation Priority

### Phase 1: Critical Fixes (High Priority)
1. Add acknowledgment responses for all message types in server
2. Configure WebSocket ping/pong keepalive in worker connection
3. Improve error logging to differentiate expected vs unexpected disconnections

### Phase 2: Enhancements (Medium Priority)
4. Add server-side periodic ping task
5. Add heartbeat ACK validation in worker
6. Implement connection stability monitoring metrics

### Phase 3: Testing (High Priority)
7. Execute all three test procedures
8. Document results and any additional issues discovered

## Expected Outcomes

After implementing these fixes:

1. **Connection Stability**: Worker maintains stable connection for extended periods (hours/days) without unexpected disconnections
2. **Reliable Job Execution**: Jobs execute successfully without connection interruptions
3. **Clear Diagnostics**: Log messages clearly indicate connection health status and distinguish normal reconnections from errors
4. **Automatic Recovery**: Temporary network issues are automatically recovered without manual intervention
5. **Windows Compatibility**: Connection remains stable on Windows platforms despite OS-level network stack behaviors

## Technical Considerations

### WebSocket Protocol on Windows

Windows TCP/IP stack may aggressively close idle connections. The combination of application-level heartbeats and WebSocket-level pings addresses this:
- Pings (20s) keep the socket active at protocol layer
- Heartbeats (60s) track worker application status
- Both are necessary for complete reliability

### AsyncIO and WebSocket Library Compatibility

The `websockets` library integrates with Python's `asyncio` event loop. Configuration parameters must be compatible with the event loop's behavior, especially on Windows where `ProactorEventLoop` is used instead of `SelectorEventLoop`.

### Message Ordering Guarantees

WebSocket provides ordered message delivery. Acknowledgments ensure messages are not only delivered but also processed by the receiver, providing end-to-end confirmation.

## Potential Risks

### Risk 1: Increased Network Traffic
**Mitigation**: Ping messages are very small (typically 2 bytes). At 20-second intervals, this adds negligible bandwidth overhead.

### Risk 2: False Positive Disconnections
**Mitigation**: Configure `ping_timeout` generously (10 seconds) to account for temporary network latency spikes.

### Risk 3: Backward Compatibility
**Mitigation**: Changes are additive (adding ACKs, adding pings). Existing behavior remains unchanged for messages that already receive ACKs.

## Success Metrics

- **Connection Uptime**: Worker maintains connection for >24 hours without unexpected disconnections
- **Job Success Rate**: 100% of scheduled jobs execute successfully (excluding script-level failures)
- **Reconnection Time**: Automatic reconnection completes within 10 seconds of disconnection
- **Error Rate**: Zero ConnectionResetError or ConnectionClosedError during normal operation
