import React, { useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, Alert } from 'react-native';
import axios from 'axios';

const API_URL = 'http://127.0.0.1:5001';

const RegisterScreen = ({ navigation }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleRegister = async () => {
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }
    try {
      setError('');
      const response = await axios.post(`${API_URL}/api/register`, {
        email,
        password,
      }, { withCredentials: true });

      if (response.status === 201) {
        Alert.alert('Success', 'Registered successfully! You are now logged in.');
        navigation.replace('Dashboard');
      }
    } catch (err) {
      const message = err.response?.data?.message || 'An error occurred during registration.';
      setError(message);
      console.error('Registration error:', err);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Register</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <TextInput
        style={styles.input}
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />
      <Button title="Register" onPress={handleRegister} />
      <Button
        title="Already have an account? Login"
        onPress={() => navigation.navigate('Login')}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 16,
  },
  title: {
    fontSize: 24,
    marginBottom: 16,
    textAlign: 'center',
  },
  input: {
    height: 40,
    borderColor: 'gray',
    borderWidth: 1,
    marginBottom: 12,
    padding: 10,
  },
  error: {
    color: 'red',
    marginBottom: 12,
    textAlign: 'center',
  },
});

export default RegisterScreen;
