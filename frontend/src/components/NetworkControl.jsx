import React, { useState, useEffect } from 'react';
import { message, Modal, InputNumber, Tooltip } from 'antd';
import planImage from '../capture/plan2.png';
import axios from 'axios';

const NetworkControl = () => {
  const [blockTime, setBlockTime] = useState({});
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [currentAuditorium, setCurrentAuditorium] = useState(null);
  const [duration, setDuration] = useState(60);
  const [unlockVisible, setUnlockVisible] = useState(false);

  const [status, setStatus] = useState({
    11: false,
    14: false,
    15: false,
    17: false,
    19: false,
    20: false,
    23: false,
    24: false,
    103: false,
    113: false,
    262: false,
  });

  const auditoriumMap = [
    { id: 11, name: 'УНЦ 11', points: '880,41 1186,41 1186,162 880,162' },
    { id: 14, name: 'УНЦ 14', points: '814,247 925,247 925,486 814,486' },
    { id: 15, name: 'УНЦ 15', points: '705,367 814,367 814,486 705,486' },
    { id: 17, name: 'УНЦ 17', points: '487,247 703,247 703,486 487,486' },
    { id: 19, name: 'УНЦ 19', points: '162,248 307,248 307,486 162,486' },
    { id: 20, name: 'УНЦ 20', points: '52,487 161,487 161,691 52,691' },
    { id: 23, name: 'УНЦ 23', points: '309,542 507,542 507,692 309,692' },
    { id: 24, name: 'УНЦ 24', points: '508,542 702,542 702,692 508,692' },
    { id: 103, name: '103', points: '1206,43 1542,43 1542,377 1206,377' },
    { id: 113, name: '113', points: '1558,43 1892,43 1892,377 1558,377' },
    { id: 262, name: '262', points: '1390,389 1724,389 1724,725 1390,725' },
  ];

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

  return (
    <div>
      <h1>Управление сетью</h1>
      <svg width="1920" height="755" style={{ border: '1px solid black' }}>
        <image href={planImage} x="0" y="0" height="100%" width="100%" />
        {auditoriumMap.map((room) => {
          const isBlocked = !status[room.id] && blockTime[room.id];
          const timeLeft =
            isBlocked &&
            Math.floor((blockTime[room.id] - (Date.now() - 3 * 60 * 60 * 1000)) / 60000);
          return (
            <Tooltip
              key={room.id}
              title={isBlocked ? `Сеть включится через ${timeLeft} минут` : null}
              color="blue"
            >
              <g>
                <polygon
                  points={room.points}
                  fill={status[room.id] ? 'lightgreen' : 'lightcoral'}
                  stroke="red"
                  strokeWidth="2"
                  onClick={() =>
                    status[room.id] ? showConfirm(room.id) : showUnlockConfirm(room.id)
                  }
                  onMouseEnter={(e) => e.target.setAttribute('fill', 'yellow')}
                  onMouseLeave={(e) =>
                    e.target.setAttribute('fill', status[room.id] ? 'lightgreen' : 'lightcoral')
                  }
                  style={{ cursor: 'pointer' }}
                />
                <text
                  x={room.points.split(' ')[0].split(',')[0]}
                  y={room.points.split(' ')[0].split(',')[1] - 10}
                  fill="black"
                  fontSize="16"
                  fontWeight="bold"
                >
                  {room.name}
                </text>
                {blockTime[room.id] && (
                  <text
                    x={room.points.split(' ')[0].split(',')[0]}
                    y={room.points.split(' ')[0].split(',')[1] + 20}
                    fill="black"
                    fontSize="14"
                  >
                    {`Разблокируется через: ${timeLeft} минут`}
                  </text>
                )}
              </g>
            </Tooltip>
          );
        })}
      </svg>
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

export default NetworkControl;
