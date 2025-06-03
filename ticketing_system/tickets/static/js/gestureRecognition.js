// Robust MediaPipe Hands + Camera integration with debug logging and gesture-to-confirm

// Debug log helper removed for production

// Gesture states
const GESTURES = {
    THUMBS_UP: 'thumbs_up',
    PEACE_SIGN: 'peace_sign',
    POINTING: 'pointing',
    NONE: 'none'
};

let hands = null;
let camera = null;
let cameraActive = false;
let currentGesture = GESTURES.NONE;

window.initializeApp = function() {
    debugLog('initializeApp called');
    // Get DOM elements
    const video = document.getElementById('camera-feed');
    const canvas = document.getElementById('output');
    const gestureStatus = document.getElementById('gesture-status');
    const confirmButton = document.getElementById('confirm-purchase');
    if (!video || !canvas || !gestureStatus || !confirmButton) {
        debugLog('Missing elements in DOM');
        return;
    }
    canvas.style.display = 'block';
    // Setup MediaPipe Hands
    hands = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
    });
    hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });
    hands.onResults((results) => {
        processHandResults(results, canvas, gestureStatus, confirmButton);
    });
    // Setup Camera
    camera = new window.Camera(video, {
        onFrame: async () => {
            if (cameraActive) {
                try {
                    await hands.send({image: video});
                } catch (e) {
                    debugLog('Error processing frame: ' + e.message);
                }
            }
        },
        width: 640,
        height: 480
    });
    // Button to start camera
    let btn1 = document.getElementById('start-camera-btn');
    let btn2 = document.getElementById('start-camera-btn-2');
    function startCam() {
        if (!cameraActive) {
            cameraActive = true;
            camera.start();
            debugLog('Camera started');
            gestureStatus.textContent = 'Camera active - show a gesture!';
            gestureStatus.className = 'alert alert-info';
        }
    }
    if (btn1) btn1.onclick = startCam;
    if (btn2) btn2.onclick = startCam;
    // Optionally stop camera
    // ...
    debugLog('App initialized. Click Start Camera to begin.');
};

function processHandResults(results, canvas, gestureStatus, confirmButton) {
    try {
        const ctx = canvas.getContext('2d');
        ctx.save();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        // Draw camera feed
        ctx.drawImage(results.image, 0, 0, canvas.width, canvas.height);
        // Draw hand landmarks
        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            for (const landmarks of results.multiHandLandmarks) {
                if (window.drawConnectors && window.HAND_CONNECTIONS) {
                    window.drawConnectors(ctx, landmarks, window.HAND_CONNECTIONS, {color: '#00FF00', lineWidth: 4});
                }
                if (window.drawLandmarks) {
                    window.drawLandmarks(ctx, landmarks, {color: '#FF0000', lineWidth: 2, radius: 3});
                }
                // Detect gesture
                let gesture = detectGesture(landmarks);
                debugLog('Detected gesture: ' + gesture);
                updateGestureStatusUI(gesture, gestureStatus, confirmButton);
            }
        } else {
            updateGestureStatusUI(GESTURES.NONE, gestureStatus, confirmButton);
        }
        ctx.restore();
    } catch (err) {
        debugLog('Error in processHandResults: ' + err.message);
    }
}

function detectGesture(landmarks) {
    // Simple rules for thumbs up, peace, pointing
    const thumbTip = landmarks[4];
    const indexTip = landmarks[8];
    const middleTip = landmarks[12];
    const ringTip = landmarks[16];
    const pinkyTip = landmarks[20];
    const wrist = landmarks[0];
    // Thumbs up: thumb above wrist, others folded
    if (
        thumbTip.y < wrist.y &&
        indexTip.y > thumbTip.y &&
        middleTip.y > thumbTip.y &&
        ringTip.y > thumbTip.y &&
        pinkyTip.y > thumbTip.y
    ) {
        return GESTURES.THUMBS_UP;
    }
    // Peace sign: index and middle above others
    if (
        indexTip.y < ringTip.y &&
        middleTip.y < ringTip.y &&
        Math.abs(indexTip.x - middleTip.x) > 0.05
    ) {
        return GESTURES.PEACE_SIGN;
    }
    // Pointing: only index above others
    if (
        indexTip.y < middleTip.y &&
        indexTip.y < ringTip.y &&
        indexTip.y < pinkyTip.y &&
        thumbTip.y > indexTip.y
    ) {
        return GESTURES.POINTING;
    }
    return GESTURES.NONE;
}

function updateGestureStatusUI(gesture, gestureStatus, confirmButton) {
    if (gesture === currentGesture) return;
    currentGesture = gesture;
    if (gesture === GESTURES.THUMBS_UP) {
        gestureStatus.textContent = '👍 Thumbs up detected! Confirming...';
        gestureStatus.className = 'alert alert-success';
        confirmButton.disabled = false;
        setTimeout(() => {
            if (currentGesture === GESTURES.THUMBS_UP) {
                confirmButton.disabled = true;
                confirmButton.form && confirmButton.form.submit();
                debugLog('Purchase confirmed via gesture!');
            }
        }, 1500);
    } else if (gesture === GESTURES.PEACE_SIGN) {
        gestureStatus.textContent = '✌️ Peace sign detected!';
        gestureStatus.className = 'alert alert-info';
        confirmButton.disabled = true;
    } else if (gesture === GESTURES.POINTING) {
        gestureStatus.textContent = '👆 Pointing detected!';
        gestureStatus.className = 'alert alert-warning';
        confirmButton.disabled = true;
    } else {
        gestureStatus.textContent = '👋 Show a gesture to confirm your purchase';
        gestureStatus.className = 'alert alert-secondary';
        confirmButton.disabled = true;
    }
}


// Update status message
function updateStatus(message, type = 'info') {
    const statusElement = document.getElementById('gesture-status');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.className = `alert alert-${type}`;
    }
}

// Don't auto-initialize, wait for the explicit call from the template
console.log('Gesture recognition script ready');

// Set up the camera
async function setupCamera() {
    console.log('Setting up camera...');
    video = document.getElementById('camera-feed');
    if (!video) {
        const error = 'Camera feed element not found';
        console.error(error);
        throw new Error(error);
    }
    // Always force canvas to show
    if (canvas) canvas.style.display = 'block'; else console.error('Canvas not found in setupCamera');

    // If camera is already running, don't request again!
    if (video.srcObject) {
        console.log('Camera already initialized, reusing existing stream.');
        updateStatus('Camera ready. Show a gesture to confirm.', 'success');
        // Show the canvas for gesture feedback
        if (canvas) canvas.style.display = 'block';
        return Promise.resolve(video);
    }
    // Setting up camera...
    
    // Get video element
    video = document.getElementById('camera-feed');
    if (!video) {
        const error = 'Camera feed element not found';
        throw new Error(error);
    }

    // Show the video element
    video.style.display = 'block';
    
    // Set up video constraints
    const constraints = {
        video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            facingMode: 'user',
            frameRate: { ideal: 30 }
        },
        audio: false
    };

    console.log('Requesting camera with constraints:', constraints);
    updateStatus('Requesting camera access...', 'info');
    
    try {
        // Request camera access
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        console.log('Got media stream:', stream);
        
        // Set the video source
        video.srcObject = stream;
        
        // Wait for the video to be ready
        return new Promise((resolve, reject) => {
            const onLoaded = () => {
                console.log('Video metadata loaded, ready state:', video.readyState);
                video.play()
                    .then(() => {
                        console.log('Video playback started');
                        updateStatus('Camera ready. Show a gesture to confirm.', 'success');
                        resolve(video);
                    })
                    .catch(playError => {
                        console.error('Error playing video:', playError);
                        reject(new Error('Could not start camera playback'));
                    });
            };

            // Set up event listeners
            video.addEventListener('loadedmetadata', onLoaded, { once: true });
            
            // Fallback in case loadedmetadata already fired
            if (video.readyState >= 1) { // HAVE_METADATA
                console.log('Video already has metadata, proceeding...');
                onLoaded();
            }
            
            // Error handling
            video.addEventListener('error', (error) => {
                console.error('Video element error:', error);
                reject(new Error('Video playback error'));
            });
            
            // Timeout if camera doesn't initialize
            const timeout = setTimeout(() => {
                console.warn('Camera initialization timeout');
                if (video.readyState < 2) { // !HAVE_CURRENT_DATA
                    reject(new Error('Camera initialization timed out'));
                }
            }, 10000);
            
            // Cleanup
            return () => {
                clearTimeout(timeout);
                video.removeEventListener('loadedmetadata', onLoaded);
            };
        });
        
    } catch (err) {
        console.error('Camera access error:', err);
        let errorMessage = 'Error accessing camera: ';
        
        if (err.name === 'NotAllowedError') {
            errorMessage = 'Camera access was denied. Please allow camera access and refresh the page.';
        } else if (err.name === 'NotFoundError' || err.name === 'OverconstrainedError') {
            errorMessage = 'No camera found or camera does not meet requirements. Please connect a camera and refresh the page.';
        } else {
            errorMessage += err.message || 'Unknown error';
        }
        
        updateStatus(errorMessage, 'danger');
        throw err;
    }
}

// Initialize hand tracking
async function initHandTracking() {
    try {
        // Check if MediaPipe Hands is available
        if (typeof window.Hands === 'undefined') {
            throw new Error('MediaPipe Hands is not available. Please refresh the page.');
        }
        
        // Create a new Hands instance
        const hands = new window.Hands({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
            }
        });

        // Configure hand tracking options
        hands.setOptions({
            maxNumHands: 1,
            modelComplexity: 1,
            minDetectionConfidence: 0.7,
            minTrackingConfidence: 0.5
        });

        // Set up the results callback
        hands.onResults(processHands);

        // Frame processing function
        let isProcessing = false;
        async function processFrame() {
            if (!isProcessing && video.readyState >= video.HAVE_ENOUGH_DATA) {
                try {
                    isProcessing = true;
                    await hands.send({ image: video });
                } catch (error) {
                    console.error('Error processing frame:', error);
                    updateStatus('Error processing video. Please refresh the page.', 'danger');
                } finally {
                    isProcessing = false;
                }
            }
            requestAnimationFrame(processFrame);
        }

        return { hands, processFrame };
        
    } catch (error) {
        console.error('Hand tracking initialization error:', error);
        throw new Error(`Failed to initialize hand tracking: ${error.message}`);
    }
}

// Process hand landmarks and detect gestures
let lastHandDetected = Date.now();

function processHands(results) {
    try {
        if (!ctx || !canvas) return;
        ctx.save();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            lastHandDetected = Date.now();
            for (const landmarks of results.multiHandLandmarks) {
                if (window.drawConnectors && window.HAND_CONNECTIONS) {
                    window.drawConnectors(ctx, landmarks, window.HAND_CONNECTIONS, { color: '#00FF00', lineWidth: 2 });
                }
                if (window.drawLandmarks) {
                    window.drawLandmarks(ctx, landmarks, { color: '#FF0000', lineWidth: 1 });
                }
                // Detect gesture
                const gesture = detectGesture(landmarks);
                console.log('Detected gesture:', gesture);
                updateGestureStatus(gesture);
            }
        } else {
            // No hand detected
            if (Date.now() - lastHandDetected > 3000) {
                updateGestureStatus('none');
                lastHandDetected = Date.now();
            }
        }
    } catch (error) {
        console.error('Error processing hands:', error);
    } finally {
        if (ctx) {
            ctx.restore();
        }
    }
}

// Simple gesture detection
function detectGesture(landmarks) {
    // Get key points
    const thumbTip = landmarks[4];
    const indexTip = landmarks[8];
    const middleTip = landmarks[12];
    const ringTip = landmarks[16];
    const pinkyTip = landmarks[20];
    const wrist = landmarks[0];

    // Check for thumbs up
    if (isThumbsUp(thumbTip, indexTip, middleTip, ringTip, pinkyTip, wrist)) {
        return GESTURES.THUMBS_UP;
    }
    
    // Check for peace sign
    if (isPeaceSign(thumbTip, indexTip, middleTip, ringTip, pinkyTip)) {
        return GESTURES.PEACE_SIGN;
    }
    
    // Check for pointing
    if (isPointing(thumbTip, indexTip, middleTip, ringTip, pinkyTip)) {
        return GESTURES.POINTING;
    }
    
    return GESTURES.NONE;
}

// Gesture detection helpers
function isThumbsUp(thumbTip, indexTip, middleTip, ringTip, pinkyTip, wrist) {
    // Thumb is extended upwards
    const thumbExtended = thumbTip.y < wrist.y - 0.1;
    
    // Other fingers are closed
    const otherFingersClosed = indexTip.y > wrist.y && 
                              middleTip.y > wrist.y && 
                              ringTip.y > wrist.y && 
                              pinkyTip.y > wrist.y;
    
    return thumbExtended && otherFingersClosed;
}

function isPeaceSign(thumbTip, indexTip, middleTip, ringTip, pinkyTip) {
    // Index and middle fingers extended
    const indexExtended = indexTip.y < thumbTip.y && indexTip.y < ringTip.y;
    const middleExtended = middleTip.y < thumbTip.y && middleTip.y < ringTip.y;
    
    // Ring and pinky fingers closed
    const ringClosed = ringTip.y > thumbTip.y;
    const pinkyClosed = pinkyTip.y > thumbTip.y;
    
    // Thumb is not extended
    const thumbNotExtended = thumbTip.x > indexTip.x;
    
    return indexExtended && middleExtended && ringClosed && pinkyClosed && thumbNotExtended;
}

function isPointing(thumbTip, indexTip, middleTip, ringTip, pinkyTip) {
    // Only index finger is extended
    const indexExtended = indexTip.y < thumbTip.y && indexTip.y < middleTip.y;
    
    // Other fingers are closed
    const otherFingersClosed = middleTip.y > thumbTip.y && 
                              ringTip.y > thumbTip.y && 
                              pinkyTip.y > thumbTip.y;
    
    return indexExtended && otherFingersClosed;
}

// Update UI based on detected gesture
let autoSubmitTimer = null;
let lastGesture = null;

function updateGestureStatus(gesture) {
    console.log('updateGestureStatus called with:', gesture);
    if (gesture === currentGesture) return;
    currentGesture = gesture;
    clearTimeout(autoSubmitTimer);
    
    switch (gesture) {
        case GESTURES.THUMBS_UP:
            gestureStatus.textContent = '👍 Thumbs up detected! Confirming in 2s...';
            gestureStatus.className = 'alert alert-success animate__animated animate__pulse';
            confirmButton.disabled = false;
            // Prevent multiple auto-submits for the same gesture
            if (lastGesture !== GESTURES.THUMBS_UP) {
                let countdown = 2;
                gestureStatus.textContent = `👍 Thumbs up detected! Confirming in ${countdown}s...`;
                autoSubmitTimer = setInterval(() => {
                    countdown--;
                    if (countdown > 0) {
                        gestureStatus.textContent = `👍 Thumbs up detected! Confirming in ${countdown}s...`;
                    } else {
                        clearInterval(autoSubmitTimer);
                        autoSubmitTimer = null;
                        gestureStatus.textContent = '👍 Purchase confirmed!';
                        // Submit the form
                        const form = document.getElementById('purchase-form');
                        if (form && !confirmButton.disabled) {
                            confirmButton.disabled = true; // Prevent double submit
                            form.submit();
                        }
                    }
                }, 1000);
            }
            lastGesture = GESTURES.THUMBS_UP;
            break;
        case GESTURES.PEACE_SIGN:
            gestureStatus.textContent = '✌️ Peace sign detected!';
            gestureStatus.className = 'alert alert-info';
            confirmButton.disabled = true;
            lastGesture = GESTURES.PEACE_SIGN;
            break;
        case GESTURES.POINTING:
            gestureStatus.textContent = '👆 Pointing detected!';
            gestureStatus.className = 'alert alert-warning';
            confirmButton.disabled = true;
            lastGesture = GESTURES.POINTING;
            break;
        default:
            gestureStatus.textContent = '👋 Show a gesture to confirm your purchase';
            gestureStatus.className = 'alert alert-secondary';
            confirmButton.disabled = true;
            lastGesture = null;
    }
}


// Initialize everything
async function init() {
    try {
        // Load MediaPipe hands model
        await setupCamera();
        const { hands, processFrame } = await initHandTracking();
        
        // Set canvas size to match video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Start processing frames
        processFrame();
        
        // Handle form submission
        document.getElementById('purchase-form').addEventListener('submit', (e) => {
            if (currentGesture !== GESTURES.THUMBS_UP) {
                e.preventDefault();
                gestureStatus.textContent = 'Please show a 👍 to confirm your purchase';
                gestureStatus.className = 'alert alert-danger';
            }
        });
        
    } catch (err) {
        console.error('Error initializing gesture recognition:', err);
        gestureStatus.textContent = 'Error initializing gesture recognition. Please try again later.';
        gestureStatus.className = 'alert alert-danger';
    }
}

// Initialize function
async function init() {
    try {
        // Get DOM elements
        video = document.getElementById('camera-feed');
        canvas = document.getElementById('output');
        ctx = canvas.getContext('2d');
        gestureStatus = document.getElementById('gesture-status');
        confirmButton = document.getElementById('confirm-purchase');
        
        if (!video || !canvas || !gestureStatus) {
            throw new Error('Required elements not found');
        }

        // Set initial status
        updateStatus('Loading gesture recognition...', 'info');

        // Initialize camera
        await setupCamera();
        
        // Set canvas size to match video
        video.onloadedmetadata = () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            updateStatus('Show a gesture to confirm your purchase', 'secondary');
        };
        
        // Initialize hand tracking
        const { hands, processFrame } = await initHandTracking();
        
        // Start processing frames
        processFrame();
        
        // Handle form submission
        const form = document.getElementById('purchase-form');
        if (form) {
            form.addEventListener('submit', (e) => {
                if (currentGesture !== GESTURES.THUMBS_UP) {
                    e.preventDefault();
                    updateStatus('Please show a 👍 to confirm your purchase', 'danger');
                }
            });
        }
        
    } catch (err) {
        console.error('Error initializing gesture recognition:', err);
        updateStatus(`Error: ${err.message || 'Failed to initialize gesture recognition'}`, 'danger');
    }
}

