import React, { useEffect, useState } from 'react';
import { View, StyleSheet, Animated, TouchableOpacity, SafeAreaView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const VoiceInterface = () => {
  const pulseAnim = new Animated.Value(1);

  useEffect(() => {
    const pulse = Animated.sequence([
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
    ]);

    Animated.loop(pulse).start();
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      {/* Centered orb */}
      <View style={styles.orbContainer}>
        <Animated.View 
          style={[
            styles.orb,
            {
              transform: [{ scale: pulseAnim }]
            }
          ]}
        />
      </View>

      {/* Bottom buttons */}
      <View style={styles.buttonContainer}>
        <TouchableOpacity style={styles.button}>
          <Ionicons name="mic" size={32} color="white" />
        </TouchableOpacity>
        <TouchableOpacity style={styles.button}>
          <Ionicons name="close" size={32} color="white" />
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
    backgroundColor: '#60A5FA',
    opacity: 0.8,
    shadowColor: '#60A5FA',
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
});

export default VoiceInterface;