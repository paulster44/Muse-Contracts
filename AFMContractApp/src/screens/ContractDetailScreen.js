import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, Button, ActivityIndicator, Linking } from 'react-native';
import axios from 'axios';

const API_URL = 'http://127.0.0.1:5001';

const ContractDetailScreen = ({ route, navigation }) => {
  const { contractId } = route.params;
  const [contract, setContract] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchContractDetails = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await axios.get(`${API_URL}/api/contracts/${contractId}`, { withCredentials: true });
      setContract(response.data);
    } catch (err) {
      setError('Failed to load contract details.');
      console.error('Fetch contract details error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContractDetails();
  }, [contractId]);

  const handleDownloadPdf = () => {
    const url = `${API_URL}/contract/pdf/${contractId}`;
    Linking.openURL(url);
  };

  if (loading) {
    return <ActivityIndicator size="large" style={{ flex: 1, justifyContent: 'center' }} />;
  }

  if (error || !contract) {
    return (
      <View style={styles.container}>
        <Text style={styles.error}>{error || 'Contract not found.'}</Text>
        <Button title="Go Back" onPress={() => navigation.goBack()} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>{contract.engagement_type || 'Contract Details'}</Text>

      <Text style={styles.label}>Engagement Date:</Text>
      <Text style={styles.value}>{contract.engagement_date}</Text>

      <Text style={styles.label}>Leader:</Text>
      <Text style={styles.value}>{contract.leader_name}</Text>

      <Text style={styles.label}>Venue:</Text>
      <Text style={styles.value}>{contract.venue_name}</Text>

      <Text style={styles.label}>Total Gross Comp:</Text>
      <Text style={styles.value}>${contract.total_gross_comp}</Text>

      <Text style={styles.title}>Side Musicians</Text>
      {contract.side_musicians.map(m => (
        <View key={m.id} style={styles.musician}>
          <Text>{m.name} ({m.instrument})</Text>
        </View>
      ))}

      <Button title="Download PDF" onPress={handleDownloadPdf} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 16,
  },
  label: {
    fontSize: 16,
    fontWeight: 'bold',
    marginTop: 8,
  },
  value: {
    fontSize: 16,
    marginBottom: 8,
  },
  musician: {
    padding: 8,
    backgroundColor: '#f0f0f0',
    marginBottom: 4,
  },
  error: {
    color: 'red',
    textAlign: 'center',
  },
});

export default ContractDetailScreen;
