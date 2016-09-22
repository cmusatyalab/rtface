
package edu.cmu.cs.gabriel.network;

import java.io.DataInputStream;
import java.io.DataOutputStream;

import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.UnknownHostException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.TreeMap;
import java.util.Vector;

import org.json.JSONException;
import org.json.JSONObject;

import edu.cmu.cs.gabriel.Const;
import edu.cmu.cs.gabriel.token.TokenController;

import android.os.Bundle;
import android.os.Handler;
import android.os.Message;
import android.util.Log;
import android.util.Pair;

public class ResultReceivingThread extends Thread {
	
	private static final String LOG_TAG = "krha";
	
	private InetAddress remoteIP;
	private int remotePort;
	private Socket tcpSocket;	
	private boolean is_running = true;
	private DataOutputStream networkWriter;
	private DataInputStream networkReader;
	
	private Handler returnMsgHandler;
	private TokenController tokenController;
	private String connection_failure_msg = "Connecting to Gabriel Server Failed. " +
			"Do you have a gabriel server running at: " + Const.GABRIEL_IP + "?";


	public ResultReceivingThread(String GABRIEL_IP,
								 int port,
								 Handler returnMsgHandler,
								 TokenController tokenController) {
		is_running = false;
		this.tokenController = tokenController;
		this.returnMsgHandler = returnMsgHandler;
		try {
			remoteIP = InetAddress.getByName(GABRIEL_IP);
		} catch (UnknownHostException e) {
			Log.e(LOG_TAG, "unknown host: " + e.getMessage());
		}
		remotePort = port;
	}

	@Override
	public void run() {
		this.is_running = true;
		Log.i(LOG_TAG, "Result receiving thread running");

		try {
			tcpSocket = new Socket();
			tcpSocket.setTcpNoDelay(true);
			tcpSocket.connect(new InetSocketAddress(remoteIP, remotePort), 5*1000);
			networkWriter = new DataOutputStream(tcpSocket.getOutputStream());
			networkReader = new DataInputStream(tcpSocket.getInputStream());
		} catch (IOException e) {
		    Log.e(LOG_TAG, Log.getStackTraceString(e));
			Log.e(LOG_TAG, "Error in initializing Data socket: " + e);
			this.notifyError(connection_failure_msg);
			this.is_running = false;
			return;
		}
		
		// Recv initial simulation information
		while(is_running == true){			
			try {
				String recvMsg = this.receiveMsg(networkReader);
				this.notifyReceivedData(recvMsg);
			} catch (IOException e) {
				Log.e("resultReceiving_thread", e.toString());
				// Do not send error to handler, Streaming thread already sent it.
				this.notifyError(e.getMessage());
				break;
			} catch (JSONException e) {
				Log.e("krha", e.toString());
				this.notifyError(e.getMessage());
			}
		}
	}

	private String receiveMsg(DataInputStream reader) throws IOException {
        int retLength = reader.readInt();
        byte[] recvByte=receiveNBytes(reader, retLength);
        String receivedString = new String(recvByte);
		return receivedString;
	}

    private byte[] receiveNBytes(DataInputStream reader, int retLength) throws IOException {
        byte[] recvByte = new byte[retLength];
        int readSize = 0;
        while(readSize < retLength){
            int ret = reader.read(recvByte, readSize, retLength-readSize);
            if(ret <= 0){
                break;
            }
            readSize += ret;
        }
        return recvByte;
    }

	private void notifyReceivedData(String recvData) throws JSONException {	
		// convert the message to JSON
		int dataSize = -1;
		String engineID = "";
		long frameID = -1;
		JSONObject header = new JSONObject(recvData);

		try{
			dataSize = header.getInt(NetworkProtocol.HEADER_MESSAGE_DATA_SIZE);
            byte[] data = receiveNBytes(networkReader, dataSize);

            Message msg = Message.obtain();
            msg.what = NetworkProtocol.NETWORK_RET_RESULT;
            msg.obj= new Pair<JSONObject, byte[]>(header, data);
            this.returnMsgHandler.sendMessage(msg);
		} catch(JSONException e){
            e.printStackTrace();
        } catch (IOException e) {
            e.printStackTrace();
        }

        try{
			frameID = header.getLong(NetworkProtocol.HEADER_MESSAGE_FRAME_ID);
			Log.d(LOG_TAG, "received response. frameID: "+frameID);
			engineID = header.getString(NetworkProtocol.HEADER_MESSAGE_ENGINE_ID);
		} catch(JSONException e){}
		
		if (frameID != -1){
			Message msg = Message.obtain();
			msg.what = NetworkProtocol.NETWORK_RET_TOKEN;
			Bundle data = new Bundle();
			data.putLong(NetworkProtocol.HEADER_MESSAGE_FRAME_ID, frameID);
			data.putString(NetworkProtocol.HEADER_MESSAGE_ENGINE_ID, engineID);
			msg.setData(data);
			this.tokenController.tokenHandler.sendMessage(msg);
		}
	}

	private void notifyError(String errorMessage) {		
		Message msg = Message.obtain();
		msg.what = NetworkProtocol.NETWORK_RET_FAILED;
		msg.obj = errorMessage;
		this.returnMsgHandler.sendMessage(msg);
	}
	
	public void close() {
		this.is_running = false;
		try {
			if(this.networkReader != null){
				this.networkReader.close();
				this.networkReader = null;
			}
		} catch (IOException e) {
		}
		try {
			if(this.networkWriter != null){
				this.networkWriter.close();
				this.networkWriter = null;
			}
		} catch (IOException e) {
		}
		try {
			if(this.tcpSocket != null){
				this.tcpSocket.shutdownInput();
				this.tcpSocket.shutdownOutput();			
				this.tcpSocket.close();	
				this.tcpSocket = null;
			}
		} catch (IOException e) {
		}
	}
}
