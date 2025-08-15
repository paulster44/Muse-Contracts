import React, { useState, useEffect } from 'react';
import { View, Text, Button, StyleSheet, FlatList, ActivityIndicator, Alert, TouchableOpacity } from 'react-native';
import axios from 'axios';

const API_URL = 'http://127.0.0.1:5001';

const DashboardScreen = ({ navigation }) => {
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchContracts = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await axios.get(`${API_URL}/api/contracts`, { withCredentials: true });
      setContracts(response.data);
    } catch (err) {
      const message = err.response?.data?.message || 'An error occurred while fetching contracts.';
      setError(message);
      console.error('Fetch contracts error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContracts();
  }, []);

  const handleLogout = async () => {
    try {
      await axios.post(`${API_URL}/api/logout`, {}, { withCredentials: true });
      Alert.alert('Success', 'Logged out successfully!');
      navigation.replace('Login');
    } catch (err) {
      Alert.alert('Error', 'Failed to log out.');
      console.error('Logout error:', err);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
        <Button title="Retry" onPress={fetchContracts} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Your Contracts</Text>
      <FlatList
        data={contracts}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <TouchableOpacity onPress={() => navigation.navigate('ContractDetail', { contractId: item.id })}>
            <View style={styles.item}>
              <Text style={styles.itemText}>{item.engagement_type || 'No Type'}</Text>
              <Text style={styles.itemText}>{item.engagement_date || 'No Date'}</Text>
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text>No contracts found.</Text>}
      />
      <Button title="Create New Contract" onPress={() => navigation.navigate('CreateContract')} />
      <Button title="Logout" onPress={handleLogout} />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    marginBottom: 16,
    textAlign: 'center',
  },
  item: {
    backgroundColor: '#f9f9f9',
    padding: 20,
    marginVertical: 8,
    borderRadius: 5,
  },
  itemText: {
    fontSize: 16,
  },
  error: {
    color: 'red',
    marginBottom: 12,
    textAlign: 'center',
  },
});

export default DashboardScreen;
