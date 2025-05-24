import React, { useEffect, useState, useRef } from 'react';
import { View, StyleSheet, Animated, TouchableOpacity, SafeAreaView, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';

const VoiceInterface = () => {
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const meterInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const pulseAnimation = useRef<Animated.CompositeAnimation | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const lastProcessedSize = useRef(0);
  const [isListening, setIsListening] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);

  // Initialize WebSocket connection
  useEffect(() => {
    ws.current = new WebSocket('ws://192.168.1.104:8000/ws');  // Replace with your IP
  
    ws.current.onopen = () => {
      console.log('WebSocket Connected');
      
      // Signal that we're ready to start a conversation
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({
          type: "start_conversation"
        }));
      }
    };
  
    ws.current.onclose = () => {
      console.log('WebSocket Disconnected');
      setIsListening(false);
    };
  
    ws.current.onerror = (error) => {
      console.error('WebSocket Error:', error);
      setIsListening(false);
      // Close the connection if it's still open
      if (ws.current && ws.current.readyState !== WebSocket.CLOSED) {
        ws.current.close();
      }
    };
  
    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Log the message type but not the full data content for audio responses
        if (data.type === 'audio_response') {
          console.log(`[WebSocket] Received ${data.type}, size: ${data.size || 'unknown'}`);
        } else {
          console.log('[WebSocket] Received:', data);
        }
        
        // Handle different message types
        switch (data.type) {
          case "start_listening":
            console.log('[WebSocket] Received command to start listening');
            startRecording();
            break;
            
          case "stop_listening":
            console.log('[WebSocket] Received command to stop listening');
            stopRecording();
            break;
            
          case "audio_response":
            // Handle incoming audio data for playback
            console.log(`[WebSocket] Received audio data of size: ${data.size || 'unknown'} bytes`);
            if (data.data && data.data.length > 0) {
              handleAudioResponse(data);
            } else {
              console.warn('[WebSocket] Received empty audio data');
            }
            break;
        }
      } catch (error) {
        console.error('[WebSocket] Error processing message:', error);
      }
    };

    // Cleanup when component unmounts
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  // Initialise audio
  useEffect(() => {
    // Request permissions and start recording when component mounts
    const initializeAudio = async () => {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        console.error('Permission to access microphone was denied');
        return;
      }
      console.log('Microphone permissions granted');
    };

    initializeAudio();
  }, [])

  // Initialise animation
  useEffect(() => {
    const startPulseAnimation = () => {
      // Stop existing animation if any
      if (pulseAnimation.current) {
        pulseAnimation.current.stop();
      }

      // Reset to initial value
      pulseAnim.setValue(1);

      // Create new pulse animation sequence
      pulseAnimation.current = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.2,
            duration: 1500,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 1500,
            useNativeDriver: true,
          })
        ])
      );
    
      // Start the animation
      pulseAnimation.current.start();
    };

    // Start pulsing animation
    startPulseAnimation();

    return () => {
      if (pulseAnimation.current) {
        pulseAnimation.current.stop();
      }
    };
  }, [])

  // Update recordingRef whenever recording state changes
  useEffect(() => {
    recordingRef.current = recording;
  }, [recording]);

  const setAudioModeForRecording = async () => {
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
    });
  };

  const setAudioModeForPlayback = async () => {
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
      staysActiveInBackground: true,
    });
  };

  // Handle incoming audio from the backend
  const handleAudioResponse = async (data: { data: string, format: string, size?: number, isComplete?: boolean, wait_for_completion?: boolean }) => {
    try {
      // If we're already playing something, we should unload it first
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }
      
      // Decode base64 data
      const base64Audio = data.data;
      const uri = `data:audio/${data.format};base64,${base64Audio}`;
      
      console.log(`[Audio] Creating sound from ${data.size || 'unknown'} bytes of data`);
      
      // Create and load the new sound
      const { sound } = await Audio.Sound.createAsync(
        { uri },
        { shouldPlay: true },
        (status) => {
          // Handle playback status updates
          if (!status.isLoaded) {
            return;
          }
          
          if (status.didJustFinish) {
            setIsPlaying(false);
            
            // Send completion notification to backend if requested
            if (data.wait_for_completion && ws.current?.readyState === WebSocket.OPEN) {
              console.log('[Audio] Sending playback completion notification');
              ws.current.send(JSON.stringify({
                type: 'playback_completed'
              }));
            }
            
            // Clean up after playback
            if (soundRef.current) {
              soundRef.current.unloadAsync();
              soundRef.current = null;
            }
          }
        }
      );
      
      // Store reference and update UI
      soundRef.current = sound;
      setIsPlaying(true);
      
      console.log('[Audio] Started playback');
      
    } catch (error) {
      console.error('[Audio] Error playing audio:', error);
      
      // Send completion notification even on error if requested
      if (data.wait_for_completion && ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({
          type: 'playback_completed'
        }));
      }
    }
  };

  const startRecording = async () => {
    try {
      // If already listening/recording, don't try to start again
      if (isListening) {
        console.log('[Recording] Recording already in progress, ignoring start request');
        return;
      }
      
      // Set listening state right away to prevent concurrent attempts
      setIsListening(true);
  
      // Make sure any existing recording is stopped first
      // await stopRecording(); // Pass false to not reset isListening
      
      // Small delay to ensure clean state
      await new Promise(resolve => setTimeout(resolve, 300));

      // Reset the processed size counter
      lastProcessedSize.current = 0;
  
      // Set audio mode for recording
      await setAudioModeForRecording();
  
      console.log('[Recording] Starting new recording...');
      const { recording: recorderInstance } = await Audio.Recording.createAsync(
        {
          android: {
            extension: '.wav',
            outputFormat: Audio.AndroidOutputFormat.DEFAULT,
            audioEncoder: Audio.AndroidAudioEncoder.DEFAULT,
            sampleRate: 16000,
            numberOfChannels: 1,
            bitRate: 16000 * 16,
          },
          ios: {
            extension: '.wav',
            outputFormat: Audio.IOSOutputFormat.LINEARPCM,
            audioQuality: Audio.IOSAudioQuality.HIGH,
            sampleRate: 16000,
            numberOfChannels: 1,
            bitRate: 16000 * 16,
          },
          web: {
            mimeType: 'audio/wav',
            bitsPerSecond: 16000 * 16,
          },
        }
      );
      
      setRecording(recorderInstance);
      console.log('[Recording] Recording instance created');
  
      // Start sending audio data in intervals
      meterInterval.current = setInterval(async () => {
        // Use recordingRef to access the current recording value
        if (recordingRef.current && ws.current?.readyState === WebSocket.OPEN) {
          try {
            const uri = await recordingRef.current.getURI();
            if (uri) {
              const response = await fetch(uri);
              const fullAudioData = await response.arrayBuffer();
              
              // Only send the new portion of the audio
              if (fullAudioData.byteLength > lastProcessedSize.current) {
                const newAudioData = fullAudioData.slice(lastProcessedSize.current);
                console.log(`[WebSocket] Sending new audio chunk: ${newAudioData.byteLength} bytes`);
                
                ws.current.send(JSON.stringify({
                  type: 'audio_data',
                  chunk: Array.from(new Uint8Array(newAudioData))
                }));

                lastProcessedSize.current = fullAudioData.byteLength;
              }
            }
          } catch (error) {
            console.error('[WebSocket] Error sending audio:', error);
          }
        }
      }, 100);
  
    } catch (err) {
      console.error('[Recording] Failed to start:', err);
      // Reset the listening state if we failed to start
      setIsListening(false);
    }
  };

  const stopRecording = async () => {
    try {
      console.log('stopRecording called, recording ref:', recordingRef.current);
      
      // Clear interval first to stop sending audio data
      if (meterInterval.current) {
        clearInterval(meterInterval.current);
        meterInterval.current = null;
      }
      
      // Check recordingRef instead of recording state
      if (recordingRef.current) {
        console.log('Stopping recording instance...');
        await recordingRef.current.stopAndUnloadAsync();
        setRecording(null);
        lastProcessedSize.current = 0;  // Reset the counter
      }

      // Set audio mode for playback
      await setAudioModeForPlayback()

    } catch (err) {
      console.error('Failed to stop recording', err);
    } finally {
      setIsListening(false);
    }
  };

  const toggleMute = async () => {
    if (isMuted) {
      await startRecording();
    } else {
      await stopRecording();
    }
    setIsMuted(!isMuted);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.orbContainer}>
        <Animated.View 
          style={[
            styles.orb,
            {
              transform: [{ scale: pulseAnim }],
              backgroundColor: isPlaying ? '#4CAF50' : '#60A5FA',
              shadowColor: isPlaying ? '#4CAF50' : '#60A5FA'
            }
          ]}
        />
        {/* <Text style={[styles.meterText, { color: wsConnected ? '#4CAF50' : '#F44336' }]}>
          WebSocket: {wsConnected ? 'Connected' : 'Disconnected'}
        </Text>
        <Text style={[styles.meterText, { color: isListening ? '#4CAF50' : '#F44336' }]}>
          Listening: {isListening ? 'Active' : 'Inactive'}
        </Text>
        <Text style={[styles.meterText, { color: isPlaying ? '#4CAF50' : '#F44336' }]}>
          Audio: {isPlaying ? 'Playing' : 'Not Playing'}
        </Text> */}
      </View>

      <View style={styles.buttonContainer}>
        <TouchableOpacity 
          style={[
            styles.button,
            isMuted && styles.activeButton
          ]} 
          onPress={toggleMute}
        >
          <Ionicons 
            name={isMuted ? "mic-off" : "mic"} 
            size={32} 
            color="white" 
          />
        </TouchableOpacity>
        <TouchableOpacity style={styles.button}>
          <Ionicons name="options" size={32} color="white" />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: 'black',
  },
  orbContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  orb: {
    width: 128,
    height: 128,
    borderRadius: 64,
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.8,
    shadowRadius: 15,
    elevation: 10,
  },
  buttonContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 48,
    paddingBottom: 64,
  },
  button: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#27272A',
    justifyContent: 'center',
    alignItems: 'center',
  },
  activeButton: {
    backgroundColor: 'grey',
  },
  meterText: {
    color: 'white',
    marginTop: 16,
    fontSize: 16,
  },
});

export default VoiceInterface;