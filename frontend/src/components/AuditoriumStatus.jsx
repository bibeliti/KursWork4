import React, { useState, useEffect } from 'react';
import { Table, Button, message, InputNumber, Modal } from 'antd';
import axios from 'axios';

const AuditoriumStatus = () => {
  const [status, setStatus] = useState({});
  const [blockTime, setBlockTime] = useState({});
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [currentAuditorium, setCurrentAuditorium] = useState(null);
  const [duration, setDuration] = useState(60);
  const [unlockVisible, setUnlockVisible] = useState(false);

  const fetchAuditoriumsStatus = async () => {
    try {
      const response = await axios.get('/api/auditoriums/status', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });
      const auditoriumsStatus = response.data;

      const initialStatus = auditoriumsStatus.reduce((acc, auditorium) => {
        acc[auditorium.auditorium_number] = auditorium.is_network_on;
        return acc;
      }, {});

      const initialBlockTime = auditoriumsStatus.reduce((acc, auditorium) => {
        if (auditorium.unlock_time) {
          acc[auditorium.auditorium_number] = new Date(auditorium.unlock_time).getTime();
        }
        return acc;
      }, {});

      setStatus(initialStatus);
      setBlockTime(initialBlockTime);
    } catch (error) {
      message.error('Ошибка при загрузке состояния аудиторий');
    }
  };

  useEffect(() => {
    fetchAuditoriumsStatus();
    const interval = setInterval(fetchAuditoriumsStatus, 10000); // Обновляем каждые 10 секунд
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setStatus((prev) => {
        const now = Date.now() - 3 * 60 * 60 * 1000; // Вычитаем 4 часа
        const newStatus = Object.keys(prev).reduce((acc, key) => {
          const unlockTime = blockTime[key];
          if (unlockTime && now >= unlockTime) {
            acc[key] = true;
          } else {
            acc[key] = prev[key];
          }
          return acc;
        }, {});
        return newStatus;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [blockTime]);

  const handleAction = async (action, auditoriumId, duration, reason = '') => {
    try {
      let response;
      if (action === 'lock') {
        response = await axios.post(
          `/api/auditoriums/${action}`,
          { number: auditoriumId, duration, reason },
          {
            headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
          }
        );
      } else if (action === 'unlock') {
        response = await axios.post(
          `/api/auditoriums/${action}`,
          { number: auditoriumId },
          {
            headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
          }
        );
      }
      message.success(response.data.message);

      setStatus((prev) => ({
        ...prev,
        [auditoriumId]: action === 'unlock',
      }));

      if (action === 'lock') {
        const blockTime = Date.now() - 3 * 60 * 60 * 1000 + duration * 60000; // Вычитаем 4 часа и конвертируем минуты в миллисекунды
        setBlockTime((prev) => ({
          ...prev,
          [auditoriumId]: blockTime,
        }));
      } else {
        setBlockTime((prev) => ({
          ...prev,
          [auditoriumId]: null,
        }));
      }
    } catch (error) {
      message.error('Ошибка при выполнении действия');
    }
  };

  const showConfirm = (auditoriumId) => {
    setCurrentAuditorium(auditoriumId);
    setConfirmVisible(true);
  };

  const handleConfirm = () => {
    handleAction('lock', currentAuditorium, duration);
    setConfirmVisible(false);
  };

  const handleCancel = () => {
    setConfirmVisible(false);
  };

  const showUnlockConfirm = (auditoriumId) => {
    setCurrentAuditorium(auditoriumId);
    setUnlockVisible(true);
  };

  const handleUnlockConfirm = () => {
    handleAction('unlock', currentAuditorium);
    setUnlockVisible(false);
  };

  const handleUnlockCancel = () => {
    setUnlockVisible(false);
  };

  const columns = [
    {
      title: 'Аудитория',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: 'Состояние',
      dataIndex: 'status',
      key: 'status',
      render: (status, record) => (
        <span style={{ color: status ? 'green' : 'red' }}>
          {status ? 'Включено' : 'Отключено'}
        </span>
      ),
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_, record) => (
        <>
          {status[record.id] ? (
            <Button type="primary" onClick={() => showConfirm(record.id)}>
              Отключить
            </Button>
          ) : (
            <Button type="primary" onClick={() => showUnlockConfirm(record.id)}>
              Включить
            </Button>
          )}
        </>
      ),
    },
  ];

  const data = Object.keys(status).map((key) => ({
    id: key,
    status: status[key],
  }));

  return (
    <div style={{ backgroundColor: '#f0f2f5', minHeight: '100vh', padding: '20px' }}>
      <h1>Состояние аудиторий</h1>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        pagination={false}
      />
      <Modal
        title="Подтверждение"
        open={confirmVisible}
        onOk={handleConfirm}
        onCancel={handleCancel}
        okText="Да"
        cancelText="Нет"
      >
        <p>Вы уверены, что хотите отключить сеть в этой аудитории?</p>
        <InputNumber
          min={1}
          defaultValue={60}
          onChange={(value) => setDuration(value)}
          addonAfter="минут"
        />
      </Modal>
      <Modal
        title="Подтверждение"
        open={unlockVisible}
        onOk={handleUnlockConfirm}
        onCancel={handleUnlockCancel}
        okText="Да"
        cancelText="Нет"
      >
        <p>Вы уверены, что хотите включить сеть в этой аудитории?</p>
      </Modal>
    </div>
  );
};

export default AuditoriumStatus;
