import React, { useEffect, useState, useRef } from 'react';
import { View, StyleSheet, Animated, TouchableOpacity, SafeAreaView, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';

const VoiceInterface = () => {
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [metering, setMetering] = useState<number>(0);
  const [wsConnected, setWsConnected] = useState(false);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const meterInterval = useRef<NodeJS.Timeout | null>(null);
  const pulseAnimation = useRef<Animated.CompositeAnimation | null>(null);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Initialize WebSocket connection
    ws.current = new WebSocket('ws://192.168.1.103:8000/ws');  // Replace with your IP

    ws.current.onopen = () => {
      console.log('WebSocket Connected');
      setWsConnected(true);
    };

    ws.current.onclose = () => {
      console.log('WebSocket Disconnected');
      setWsConnected(false);
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket Error:', error);
      if (ws.current) {
        console.log('Current WebSocket URL:', ws.current.url);
      }
      setWsConnected(false);
    };

    // Request permissions and start recording when component mounts
    const initializeAudio = async () => {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        console.error('Permission to access microphone was denied');
        return;
      }

      startRecording();
    };

    initializeAudio();

    // Start pulsing animation
    startPulseAnimation();

    // Cleanup when component unmounts
    return () => {
      if (recording) {
        recording.stopAndUnloadAsync();
      }
      if (meterInterval.current) {
        clearInterval(meterInterval.current);
      }
      if (pulseAnimation.current) {
        pulseAnimation.current.stop();
      }
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

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

  const startRecording = async () => {
    try {
      if (recording) {
        console.log('Already recording, stopping first...');
        await recording.stopAndUnloadAsync();
        setRecording(null);
        if (meterInterval.current) {
          clearInterval(meterInterval.current);
        }
      }
  
      // Configure audio mode for recording
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
  
      console.log('Starting recording...');
      const { recording: recorderInstance } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY,
        (status) => {
          if (status.metering !== undefined) {
            setMetering(status.metering);
            
            // Send metering data to server for testing
            if (ws.current && ws.current.readyState === WebSocket.OPEN) {
              ws.current.send(JSON.stringify({
                type: 'audio_metering',
                value: status.metering
              }));
            }
          }
        },
        100 // Update interval in milliseconds
      );
      
      setRecording(recorderInstance);
  
      // Start metering updates
      meterInterval.current = setInterval(async () => {
        if (recorderInstance) {
          const status = await recorderInstance.getStatusAsync();
          if (status.metering !== undefined) {
            setMetering(status.metering);
            
            // Send audio data if WebSocket is connected
            if (ws.current && ws.current.readyState === WebSocket.OPEN) {
              const uri = await recorderInstance.getURI();
              if (uri) {
                // Log that we're sending data
                console.log('Sending audio data to server...');
                
                ws.current.send(JSON.stringify({
                  type: 'audio_data',
                  uri: uri,
                  metering: status.metering
                }));
              }
            }
          }
        }
      }, 100);
  
    } catch (err) {
      console.error('Failed to start recording', err);
    }
  };

  const stopRecording = async () => {
    try {
      if (!recording) return;

      console.log('Stopping recording...');
      if (meterInterval.current) {
        clearInterval(meterInterval.current);
        meterInterval.current = null;
      }
      
      await recording.stopAndUnloadAsync();
      setMetering(-160); // Reset metering to minimum when stopped
      setRecording(null);
    } catch (err) {
      console.error('Failed to stop recording', err);
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

  // Normalize metering value to a scale we can use
  const normalizedMeter = Math.max(0, (metering + 160) / 160);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.orbContainer}>
        <Animated.View 
          style={[
            styles.orb,
            {
              transform: [{ scale: pulseAnim }],
              backgroundColor: '#60A5FA',
              shadowColor: '#60A5FA',
              opacity: isMuted ? 0.4 : (0.4 + (normalizedMeter * 0.6)),
            }
          ]}
        />
        <Text style={styles.meterText}>
          Level: {normalizedMeter.toFixed(2)}
        </Text>
        <Text style={[styles.meterText, { color: wsConnected ? '#4CAF50' : '#F44336' }]}>
          WebSocket: {wsConnected ? 'Connected' : 'Disconnected'}
        </Text>
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