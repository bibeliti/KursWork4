import React, { useState } from 'react';
import { Button, Input, Form, message } from 'antd';
import axios from 'axios';

const Login = ({ onLogin }) => {
  const [loading, setLoading] = useState(false);

  const handleLogin = async (values) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      const emailWithDomain = values.email.includes('@') ? values.email : `${values.email}@example.com`;
      params.append('username', emailWithDomain);
      params.append('password', values.password);

      const response = await axios.post('/api/auth/jwt/login', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      localStorage.setItem('token', response.data.access_token);
      onLogin();
      message.success('Login successful');
    } catch (error) {
      if (error.response) {
        const { status, data } = error.response;
        if (status === 401) {
          message.error('Invalid email or password');
        } else {
          message.error(`Login failed: ${data.detail || 'Unknown error'}`);
        }
      } else {
        message.error('Unable to connect to the server');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
      backgroundColor: '#f0f2f5',
    }}>
      <div style={{
        width: 300,
        padding: 24,
        borderRadius: 8,
        backgroundColor: '#fff',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
      }}>
        <h1 style={{ textAlign: 'center' }}>Login</h1>
        <Form onFinish={handleLogin}>
          <Form.Item
            name="email"
            rules={[{ required: true, message: 'Please input your email!' }]}
          >
            <Input placeholder="Email" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Please input your password!' }]}
          >
            <Input.Password placeholder="Password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Login
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
};

export default Login;
