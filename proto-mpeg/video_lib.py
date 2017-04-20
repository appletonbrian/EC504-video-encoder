import proto_mpeg
import time
import numpy as np
from bitstring import BitStream
from bitstring import BitArray, ReadError
import huffman_mpeg as codes
import matplotlib.pyplot as plt
import motion as mot


def encodeMot(mot_vec,nbits):
	'''
	Encodes mot_vec into bits
	
	mot_vec: array of motion vectors (3D - where the 3rd dim represents X and Y coordinates)
	nbits: number of bits to encode every integer
	
	Returns
	out: binary represantion of motion array
	'''
	out=BitArray()
	mot_vec=mot_vec.reshape([-1])
	for k in range(len(mot_vec)):
		out.append('0b'+np.binary_repr(mot_vec[k],width=nbits))
	return out
	
def decodeMot(mot_bin,nbits,w,l):
	'''
	mot_bin: binary file for motion vectors
	nbits: number of bits to decode every integer
	w:required width
	l:required length
	
	Returns
	mot_vec: array of motion vectors of size (w,l,2) (2 dims for X and Y coordinates of the motion
	'''
	mot_vec = np.zeros(w*l*2)
	for k in range(len(mot_vec)):
		mot_vec[k]=mot_bin[k*nbits:(k+1)*nbits].uint
	return mot_vec.reshape([w,l,2]).astype(int)
		
		
def encodeVideo(outname,fname,nframes=-1,mot_est='none',mot_clip=100,Ssize=7):
	'''
	Encodes the frames in 'fname' into a single file and saves is in 'outname'
	
	outname:output file name
	fnmae:folder directory which includes jpg images
	nframes:number of framse to encode. If it is equal to -1, encode all frames
	mot_est: Algorithm to use for motion estimation. Choose between 
			'none' No motion estimation			
			'frame_difference' Code differences of consecutive frames
			'block_matching' Apply block matching algorithm
	mot_clip: motion array will be squezeed to (-mot_clip,mot_clip)
	Ssize: Size of search window
	
	Returns
	Nothing
	
	'''
	images = proto_mpeg.get_jpegs(fname,nframes)#[0]
	output=BitArray()
	# Create a frame object initialized with our image
	print("Encoding image-1")
	t=time.time()
	frame = proto_mpeg.frame(images[0])
	# Retreive the binary encoding of the image
	output.append(frame.encode_to_bits())
	# Append an end of frame character
	output.append('0b' + codes.EOF)
	print(str(time.time()-t)+' seconds')
	for k in range(1,len(images)):
		# Create a frame object initialized with our image
		print("Encoding image-"+str(k+1))
		t=time.time()
		if(mot_est=='none'):
			code=images[k]
		else:
			if(mot_est=='frame_difference'):
				err=images[k].astype(int)-images[k-1].astype(int)
			elif(mot_est=='block_matching'):
				mot_vec,err = mot.blockMatching(images[k-1],images[k],Bsize=8,Ssize=Ssize)
			err[err<-mot_clip]=-mot_clip
			err[err>mot_clip]=mot_clip
			code=(err+mot_clip).astype(np.uint8)
		frame = proto_mpeg.frame(code)
		# Retreive the binary encoding of the image
		output.append(frame.encode_to_bits())
		output.append('0b' + codes.EOF)
		
		if(mot_est=='block_matching'):
			mot_vec = mot_vec+Ssize
			nbits = int(np.ceil(np.log2(2*Ssize+1)))
			mot_bin=encodeMot(mot_vec,nbits)
			output.append(mot_bin)
			output.append('0b' + codes.EOF)
		# Append an end of frame character
		
		print(str(time.time()-t)+' seconds')

	f = open(outname, 'wb')
	output.tofile(f)
	f.close()
	del frame
	
def playVideo(fname,realTime=True,size=[432,720],mot_est='none',mot_clip=100,Ssize=7):
	'''
	Decodes and plays the video in 'fname'
	
	fnmae:input file name
	realTime: Boolean, if true show each frame after decoding, if false first decode 
				all of the frames then show them
	size: Size of the frames
	mot_est: Algorithm to use for motion estimation. Choose between 
			'none' No motion estimation			
			'frame_difference' Code differences of consecutive frames
			'block_matching' Apply block matching algorithm
	mot_clip: motion array will be squezeed to (-mot_clip,mot_clip)
	Ssize: Size of search window
	
	Returns
	Nothing
	
	'''
	f = open(fname, 'rb')
	decoded_bits = BitStream(f)

	plt.ion()
	ax = plt.gca()
	ax.axis('off')
	fig = plt.gcf()
	fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
	fig.canvas.set_window_title("EC504 Viewer")
	plt.pause(.001)
	
	k=1
	prev_image=mot_clip*np.ones([size[0],size[1],3]).astype(np.uint8)
	frames=list()
	while(True):
		# Read the stream up to the end of frame (EOF) character.
		try:
			framebits = decoded_bits.readto('0b' + codes.EOF)[:-1*len(codes.EOF)]
		except ReadError:
			break
		print("Decoding image-"+str(k))
		k+=1	
		t=time.time()
		# Create a frame object from the proto_mpeg library
		frame = proto_mpeg.frame()
		# Decode the bits and reconstruct the image
		frame.decode_from_bits(framebits, int(size[1]/16), int(size[0]/16))
		code = frame.getFrame()
		if(mot_est=='none'):
			image=code
		elif(mot_est=='frame_difference'):
			image=(prev_image.astype(int)+code.astype(int)-mot_clip).astype(np.uint8)
			prev_image=image
		elif(mot_est=='block_matching'):
			if(k==2):
				image=code
			else:
				nbits = int(np.ceil(np.log2(2*Ssize+1)))
				motbits = decoded_bits.read(int(size[0]/8)*int(size[1]/8)*2*nbits)
				tmp = decoded_bits.readto('0b' + codes.EOF)
				mot_arr=decodeMot(motbits,nbits,int(size[0]/8), int(size[1]/8))-Ssize			
				prev_image_w=mot.wrap(prev_image,mot_arr)
				image=(prev_image_w.astype(int)-code.astype(int)+mot_clip).astype(np.uint8)
			prev_image=image
		print(str(time.time()-t)+' seconds')
		if(realTime):
			plt.imshow(image, extent=(0, 1, 1, 0))
			plt.draw()
			plt.pause(.001)
		else:
			frames.append(image)
		del frame
	f.close()
	if(not realTime):
		for k in range(len(frames)):
			image=frames[k]
			plt.imshow(image, extent=(0, 1, 1, 0))
			plt.draw()
			plt.pause(1)
	input("Press [enter] to continue.")
