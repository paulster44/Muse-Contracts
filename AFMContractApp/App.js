import 'react-native-gesture-handler';
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import LoginScreen from './src/screens/LoginScreen';
import RegisterScreen from './src/screens/RegisterScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import CreateContractScreen from './src/screens/CreateContractScreen';
import ContractDetailScreen from './src/screens/ContractDetailScreen';

const Stack = createStackNavigator();

const App = () => {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Login">
        <Stack.Screen name="Login" component={LoginScreen} />
        <Stack.Screen name="Register" component={RegisterScreen} />
        <Stack.Screen name="Dashboard" component={DashboardScreen} />
        <Stack.Screen name="CreateContract" component={CreateContractScreen} options={{ title: 'New Contract' }} />
        <Stack.Screen name="ContractDetail" component={ContractDetailScreen} options={{ title: 'Contract Details' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
};

export default App;
