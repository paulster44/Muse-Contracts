import React, { useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, ScrollView, Switch } from 'react-native';
import axios from 'axios';

const API_URL = 'http://127.0.0.1:5001';

const CreateContractScreen = ({ navigation }) => {
  const [step, setStep] = useState(1);
  const [contract, setContract] = useState({
    engagement_date: '',
    start_time: '',
    end_time: '',
    leader_name: '',
    leader_card_no: '',
    leader_address: '',
    leader_phone: '',
    leader_ssn_ein: '',
    band_name: '',
    venue_name: '',
    location_borough: '',
    engagement_type: '',
    pre_heat_hours: '0',
    num_musicians: '1',
    actual_hours_engagement: '0',
    has_rehearsal: false,
    actual_hours_rehearsal: '0',
    is_recorded: false,
    leader_is_incorporated: false,
    side_musicians: [],
  });
  const [newContractId, setNewContractId] = useState(null);

  const handleInputChange = (field, value) => {
    setContract({ ...contract, [field]: value });
  };

  const nextStep = () => setStep(step + 1);
  const prevStep = () => setStep(step - 1);

  const createDraftContract = async () => {
    try {
      const response = await axios.post(`${API_URL}/api/contracts`, {}, { withCredentials: true });
      if (response.status === 201) {
        setNewContractId(response.data.id);
        nextStep();
      }
    } catch (error) {
      console.error('Error creating draft contract', error);
      Alert.alert('Error', 'Failed to create a draft contract. Please try again.');
    }
  };

  const submitContract = async () => {
    try {
        const response = await axios.put(`${API_URL}/api/contracts/${newContractId}`, contract, { withCredentials: true });
        if (response.status === 200) {
            Alert.alert('Success', 'Contract submitted successfully!');
            navigation.navigate('Dashboard');
        }
    } catch (error) {
        console.error('Error submitting contract', error);
        Alert.alert('Error', 'Failed to submit the contract. Please try again.');
    }
  };


  const renderStep1 = () => (
    <ScrollView>
      <Text style={styles.title}>Step 1: Engagement Details</Text>
      <TextInput placeholder="Engagement Date (YYYY-MM-DD)" value={contract.engagement_date} onChangeText={(val) => handleInputChange('engagement_date', val)} style={styles.input} />
      <TextInput placeholder="Start Time (HH:MM)" value={contract.start_time} onChangeText={(val) => handleInputChange('start_time', val)} style={styles.input} />
      <TextInput placeholder="End Time (HH:MM)" value={contract.end_time} onChangeText={(val) => handleInputChange('end_time', val)} style={styles.input} />
      <TextInput placeholder="Leader Name" value={contract.leader_name} onChangeText={(val) => handleInputChange('leader_name', val)} style={styles.input} />
      <TextInput placeholder="Leader Card No." value={contract.leader_card_no} onChangeText={(val) => handleInputChange('leader_card_no', val)} style={styles.input} />
      <TextInput placeholder="Leader Address" value={contract.leader_address} onChangeText={(val) => handleInputChange('leader_address', val)} style={styles.input} />
      <TextInput placeholder="Leader Phone" value={contract.leader_phone} onChangeText={(val) => handleInputChange('leader_phone', val)} style={styles.input} />
      <TextInput placeholder="Leader SSN or EIN" value={contract.leader_ssn_ein} onChangeText={(val) => handleInputChange('leader_ssn_ein', val)} style={styles.input} />
      <TextInput placeholder="Band Name" value={contract.band_name} onChangeText={(val) => handleInputChange('band_name', val)} style={styles.input} />
      <TextInput placeholder="Venue Name" value={contract.venue_name} onChangeText={(val) => handleInputChange('venue_name', val)} style={styles.input} />
      <TextInput placeholder="Location (Borough/Area)" value={contract.location_borough} onChangeText={(val) => handleInputChange('location_borough', val)} style={styles.input} />
      <TextInput placeholder="Engagement Type" value={contract.engagement_type} onChangeText={(val) => handleInputChange('engagement_type', val)} style={styles.input} />
      <TextInput placeholder="Pre-Heat Hours" value={contract.pre_heat_hours} onChangeText={(val) => handleInputChange('pre_heat_hours', val)} keyboardType="numeric" style={styles.input} />
      <Button title="Next" onPress={createDraftContract} />
    </ScrollView>
  );

  const handleSideMusicianChange = (index, field, value) => {
    const updatedSideMusicians = [...contract.side_musicians];
    updatedSideMusicians[index][field] = value;
    handleInputChange('side_musicians', updatedSideMusicians);
  };

  const addSideMusician = () => {
    handleInputChange('side_musicians', [...contract.side_musicians, { name: '', instrument: '', tax_id: '', card_no: '', is_doubling: false, has_cartage: false }]);
  };

  const renderStep2 = () => (
    <ScrollView>
      <Text style={styles.title}>Step 2: Musician & Engagement Details</Text>
      <TextInput placeholder="Actual Paid Hours of Engagement" value={contract.actual_hours_engagement} onChangeText={(val) => handleInputChange('actual_hours_engagement', val)} keyboardType="numeric" style={styles.input} />
      <View style={styles.switchContainer}>
        <Text>Is there a Rehearsal?</Text>
        <Switch value={contract.has_rehearsal} onValueChange={(val) => handleInputChange('has_rehearsal', val)} />
      </View>
      {contract.has_rehearsal && (
        <TextInput placeholder="Actual Paid Hours of Rehearsal" value={contract.actual_hours_rehearsal} onChangeText={(val) => handleInputChange('actual_hours_rehearsal', val)} keyboardType="numeric" style={styles.input} />
      )}
      <View style={styles.switchContainer}>
        <Text>Will performance be Recorded/Reproduced/Transmitted?</Text>
        <Switch value={contract.is_recorded} onValueChange={(val) => handleInputChange('is_recorded', val)} />
      </View>
      <View style={styles.switchContainer}>
        <Text>Is the Leader/Employer signing as an incorporated entity?</Text>
        <Switch value={contract.leader_is_incorporated} onValueChange={(val) => handleInputChange('leader_is_incorporated', val)} />
      </View>

      <Text style={styles.title}>Side Musicians</Text>
      <TextInput placeholder="Number of Musicians" value={contract.num_musicians} onChangeText={(val) => handleInputChange('num_musicians', val)} keyboardType="numeric" style={styles.input} />

      {contract.side_musicians.map((musician, index) => (
        <View key={index} style={styles.musicianContainer}>
          <Text>Side Musician {index + 1}</Text>
          <TextInput placeholder="Name" value={musician.name} onChangeText={(val) => handleSideMusicianChange(index, 'name', val)} style={styles.input} />
          <TextInput placeholder="Instrument" value={musician.instrument} onChangeText={(val) => handleSideMusicianChange(index, 'instrument', val)} style={styles.input} />
        </View>
      ))}
      <Button title="Add Side Musician" onPress={addSideMusician} />

      <Button title="Back" onPress={prevStep} />
      <Button title="Submit" onPress={submitContract} />
    </ScrollView>
  );

  return (
    <View style={styles.container}>
      {step === 1 && renderStep1()}
      {step === 2 && renderStep2()}
    </View>
  );
};

const styles = StyleSheet.create({
    container: {
      flex: 1,
      padding: 20,
    },
    title: {
      fontSize: 22,
      fontWeight: 'bold',
      marginBottom: 20,
      textAlign: 'center',
    },
    input: {
      backgroundColor: '#fff',
      borderWidth: 1,
      borderColor: '#ddd',
      padding: 10,
      fontSize: 18,
      borderRadius: 6,
      marginBottom: 10,
    },
    switchContainer: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 15,
    },
    musicianContainer: {
        marginBottom: 15,
        padding: 10,
        borderWidth: 1,
        borderColor: '#ddd',
        borderRadius: 6,
    },
});

export default CreateContractScreen;
