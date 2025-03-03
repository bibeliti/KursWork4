import React, { useState } from 'react';
import { Layout, Menu } from 'antd';
import NetworkControl from './components/NetworkControl';
import Login from './components/Login';
import AuditoriumStatus from './components/AuditoriumStatus';

const { Header, Content } = Layout;

const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'));
  const [selectedTab, setSelectedTab] = useState('network');

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsLoggedIn(false);
  };

  const handleMenuClick = (e) => {
    setSelectedTab(e.key);
  };

  return (
    <Layout>
      <Header>
        <Menu theme="dark" mode="horizontal" onClick={handleMenuClick} selectedKeys={[selectedTab]}>
          <Menu.Item key="network">Управление сетью</Menu.Item>
          <Menu.Item key="status">Состояние аудиторий</Menu.Item>
          {isLoggedIn && <Menu.Item key="logout" onClick={handleLogout}>Выход из системы</Menu.Item>}
        </Menu>
      </Header>
      <Content style={{ padding: '0 50px', marginTop: 64 }}>
        {isLoggedIn ? (
          selectedTab === 'network' ? (
            <NetworkControl />
          ) : (
            <AuditoriumStatus />
          )
        ) : (
          <Login onLogin={() => setIsLoggedIn(true)} />
        )}
      </Content>
    </Layout>
  );
};

export default App;
